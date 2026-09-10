"""MarketBridge read-only API and same-origin dashboard host."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
import secrets
import time

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .evaluation import evaluate_all
from .incidents import incident_reconstruction
from .kalshi import TRACKED_KALSHI_SYMBOLS, get_kalshi_pulse
from .live import get_live_snapshot
from .market_data import HistoricalMarketDataService
from .market_data.models import MarketDataError, Range, Resolution, Session
from .metrics import PASSPORT_VERIFICATION_FAILURE, REPLAY_MISMATCH, observe_risk_check
from .news import TRACKED_NEWS_SYMBOLS, get_market_news
from .risk import ReplayRequest, RiskCheckRequest, RiskGateway
from .risk.models import OutcomeRequest
from .risk.passport import PassportStore
from .scenarios import list_scenarios, run_scenario
from .security import NonceStore, SignatureHeaders, SlidingWindowLimiter, verify_signature
from .shadow import LivePipeline, TRACKED_SYMBOLS
from .symbols import ActiveSubscriptions, NASDAQ_STOCK_UNIVERSE, SymbolCatalog

ROOT = Path(__file__).resolve().parents[2]
WEB = Path(os.environ.get("MARKETBRIDGE_WEB_DIR", str(ROOT / "apps" / "web" / "out"))).resolve()
symbol_catalog = SymbolCatalog(Path(os.environ.get("MARKETBRIDGE_SYMBOL_DB", ROOT / "artifacts" / "nasdaq-symbols.sqlite3")))
active_subscriptions = ActiveSubscriptions(TRACKED_SYMBOLS)
pipeline = LivePipeline(ROOT / "artifacts" / "shadow-decisions.jsonl", active_subscriptions=active_subscriptions)
risk_gateway = RiskGateway(ROOT, symbol_catalog=symbol_catalog)
historical_market_data = HistoricalMarketDataService.from_environment()
nonce_store = NonceStore(ttl_seconds=30)
integration_limiter = SlidingWindowLimiter(limit=300, window_seconds=60)
ws_limiter = SlidingWindowLimiter(limit=20, window_seconds=60)


def _allowed_origins() -> list[str]:
    configured = [item.strip() for item in os.environ.get("MARKETBRIDGE_ALLOWED_ORIGINS", "").split(",") if item.strip()]
    return configured or [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


ALLOWED_ORIGINS = _allowed_origins()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        await asyncio.to_thread(symbol_catalog.ensure_fresh)
    except Exception:
        # Keep the last verified catalogue (or the built-in bootstrap set) when
        # Nasdaq's public directory is temporarily unavailable.
        pass
    pipeline.start()
    try:
        yield
    finally:
        pipeline.stop()


app = FastAPI(
    title="MarketBridge API",
    version="1.0.0",
    description="Market truth, exposure-aware order safety, and replayable proof for 24/7 equity perpetuals.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Accept", "Content-Type", "X-MarketBridge-Key", "X-MarketBridge-Timestamp",
        "X-MarketBridge-Nonce", "X-MarketBridge-Signature",
    ],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # Next's static export includes inline bootstrap payloads. Keep API responses
    # strict while allowing those generated scripts on HTML documents.
    script_policy = (
        "script-src 'self' 'unsafe-inline';"
        if response.headers.get("content-type", "").startswith("text/html")
        else "script-src 'self';"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        f"{script_policy} connect-src 'self' https: wss:; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.url.scheme == "https" or os.environ.get("MARKETBRIDGE_FORCE_HSTS") == "1":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "data_modes": ["SYNTHETIC_DEMO", "SYNTHETIC_TEST", "HISTORICAL_RECONSTRUCTION", "LIVE_RESEARCH", "SHADOW_ORACLE"],
        "web_ready": (WEB / "index.html").exists(),
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    readiness = pipeline.readiness()
    return JSONResponse(status_code=200 if readiness["ready"] else 503, content=readiness)


@app.get("/health/feeds")
def health_feeds():
    snap = pipeline.snapshot()
    return {
        "providers": snap["providers"],
        "generation": snap["generation"],
        "market_health": snap["market_health"],
        "configuration": snap["configuration"],
    }


@app.get("/v1/demo/scenarios")
def scenarios():
    return {
        "scenarios": list_scenarios(),
        "symbols": [
            {"symbol": "NVDA", "name": "NVIDIA", "base_price": 182.5},
            {"symbol": "TSLA", "name": "Tesla", "base_price": 346.8},
        ],
        "data_mode": "SYNTHETIC_TEST",
    }


@lru_cache(maxsize=12)
def _trace(scenario_id: str, symbol: str):
    return run_scenario(scenario_id, symbol)


@app.get("/v1/demo/scenarios/{scenario_id}")
def scenario(scenario_id: str, symbol: str = Query(default="NVDA", max_length=8)):
    if scenario_id not in {item["id"] for item in list_scenarios()} or symbol not in {"NVDA", "TSLA"}:
        raise HTTPException(status_code=404, detail="Unknown scenario or symbol")
    return _trace(scenario_id, symbol)


@lru_cache(maxsize=1)
def _evaluation():
    return evaluate_all()


@app.get("/v1/demo/evaluation")
def evaluation():
    return _evaluation()


@app.get("/v1/incidents/sk-hynix-july-2026")
def historical_incident():
    return incident_reconstruction()


@app.get("/v1/live/snapshot")
def live_snapshot(refresh: bool = Query(default=False)):
    return get_live_snapshot(force=refresh)


class ActiveSymbolRequest(BaseModel):
    reason: str = Field(default="view", pattern="^(view|watchlist|position|order|recent)$")


def _display_data_configured() -> bool:
    return bool(os.environ.get("ALPACA_API_KEY", "").strip() and os.environ.get("ALPACA_SECRET_KEY", "").strip())


@app.get("/v1/symbols")
def nasdaq_symbols(
    query: str = Query(default="", max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    items, total = symbol_catalog.search(query, limit=limit, offset=offset)
    active = set(active_subscriptions.symbols(30))
    return {
        **symbol_catalog.status(),
        "query": query,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [item.as_json(active=item.symbol in active, display_data=_display_data_configured(), standard_policy=item.symbol in risk_gateway.assets) for item in items],
    }


@app.get("/v1/symbols/{symbol}")
def nasdaq_symbol(symbol: str):
    item = symbol_catalog.get(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown Nasdaq symbol")
    active = item.symbol in set(active_subscriptions.symbols(30))
    return item.as_json(active=active, display_data=_display_data_configured(), standard_policy=item.symbol in risk_gateway.assets)


@app.post("/v1/market/active-symbols/{symbol}")
def activate_market_symbol(symbol: str, payload: ActiveSymbolRequest):
    item = symbol_catalog.get(symbol)
    if item is None:
        raise HTTPException(status_code=404, detail="Unknown Nasdaq symbol")
    active_subscriptions.touch(item.symbol, payload.reason)
    return {"accepted": True, "symbol": item.symbol, "reason": payload.reason, **active_subscriptions.snapshot()}


@app.get("/v1/market/active-symbols")
def market_active_symbols():
    return active_subscriptions.snapshot()


@app.get("/v1/news")
def market_news(
    symbol: str | None = Query(default=None, min_length=1, max_length=8, pattern="^[A-Za-z]+$"),
):
    normalized = symbol.upper() if symbol else None
    if normalized and normalized not in TRACKED_NEWS_SYMBOLS:
        raise HTTPException(status_code=404, detail="Unknown news symbol")
    return get_market_news(symbol=normalized)


@app.get("/v1/kalshi/pulse")
def kalshi_pulse(
    symbol: str = Query(min_length=1, max_length=8, pattern="^[A-Za-z]+$"),
):
    """Public Kalshi event probabilities; never eligible as direct price evidence."""
    normalized = symbol.upper()
    if normalized not in TRACKED_KALSHI_SYMBOLS:
        raise HTTPException(status_code=404, detail="Unknown Kalshi pulse symbol")
    return get_kalshi_pulse(normalized)


@app.get("/v1/market/bars/{symbol}")
async def historical_bars(
    symbol: str,
    range_: Range = Query(default=Range.DAY_5, alias="range"),
    resolution: Resolution | None = Query(default=None),
    feed: str = Query(default="iex"),
    adjustment: str = Query(default="raw"),
    session: Session = Query(default=Session.REGULAR),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
):
    """Sanitized display bars. This endpoint never feeds oracle qualification."""
    try:
        return await historical_market_data.bars(
            symbol, selected_range=range_, resolution=resolution, feed=feed.lower(),
            adjustment=adjustment.lower(), session=session, start=start, end=end,
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


@app.get("/v1/market/snapshots")
async def display_snapshots(
    symbols: str | None = Query(default=None, max_length=240),
    feed: str = Query(default="iex"),
):
    """Batch display quotes for the curated universe; never oracle evidence."""
    requested = tuple(dict.fromkeys(
        item.strip().upper() for item in (symbols.split(",") if symbols else NASDAQ_STOCK_UNIVERSE) if item.strip()
    ))
    if len(requested) > 30 or any(symbol_catalog.get(symbol) is None for symbol in requested):
        raise HTTPException(status_code=422, detail="Only the curated 30-stock Nasdaq universe is supported")
    try:
        snapshots = await historical_market_data.snapshots(requested, feed=feed.lower())
    except MarketDataError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc
    return {
        "provider": "alpaca", "feed": feed.lower(), "data_role": "DISPLAY_ONLY_NOT_ORACLE_EVIDENCE",
        "items": [
            {
                "symbol": symbol,
                "name": symbol_catalog.get(symbol).name,
                "exchange": "NASDAQ",
                "currency": "USD",
                **snapshots[symbol],
            }
            for symbol in requested
        ],
    }


@app.get("/v1/shadow/snapshot")
def shadow_snapshot():
    return pipeline.snapshot()


@app.get("/v1/ml/status")
def ml_status():
    """Return loaded model provenance and enforcement boundary."""
    return pipeline.oracle.ai_status()


@app.get("/v1/ml/evaluation")
def ml_evaluation():
    """Expose the latest offline ML evaluation artifact when present."""
    path = ROOT / "reports" / "ml-evaluation.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run scripts/train_ai_models.py first")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/v1/shadow/refresh")
def refresh_shadow_yahoo():
    return pipeline.refresh_yahoo()


@app.get("/v1/shadow/stream")
def shadow_stream():
    """Event-driven SSE fallback. No fixed 100 ms polling loop."""
    def events():
        generation = -1
        while True:
            snapshot = pipeline.wait_for_generation(generation, timeout=10)
            if snapshot["generation"] != generation:
                generation = snapshot["generation"]
                yield f"data:{json.dumps(snapshot, allow_nan=False, separators=(',', ':'))}\n\n"
            else:
                yield ":keepalive\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})


@app.websocket("/v1/shadow/ws")
async def shadow_websocket(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    host = websocket.client.host if websocket.client else "unknown"
    if not ws_limiter.allow(host):
        await websocket.close(code=1013, reason="Too many connection attempts")
        return
    await websocket.accept()
    generation = -1
    try:
        while True:
            snapshot = await asyncio.to_thread(pipeline.wait_for_generation, generation, 10.0)
            if snapshot["generation"] != generation:
                generation = snapshot["generation"]
                await websocket.send_json({"type": "shadow_snapshot", "data": snapshot})
            else:
                await websocket.send_json({"type": "heartbeat", "generation": generation})
    except WebSocketDisconnect:
        return


class MochatradeMarketEvent(BaseModel):
    symbol: str = Field(pattern="^(NVDA|TSLA|AAPL|MSFT|AMD)$")
    mark_price: float = Field(gt=0, lt=1_000_000)
    oracle_price: float | None = Field(default=None, gt=0, lt=1_000_000)
    mid_price: float | None = Field(default=None, gt=0, lt=1_000_000)
    best_bid: float | None = Field(default=None, gt=0, lt=1_000_000)
    best_ask: float | None = Field(default=None, gt=0, lt=1_000_000)
    open_interest: float | None = Field(default=None, ge=0)
    funding: float | None = Field(default=None, ge=-1, le=1)
    volume: float | None = Field(default=None, ge=0)
    event_time: datetime


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _authenticate_integration(
    request: Request,
    x_marketbridge_key: str | None,
    x_marketbridge_timestamp: str | None,
    x_marketbridge_nonce: str | None,
    x_marketbridge_signature: str | None,
) -> None:
    client = _client_key(request)
    if not integration_limiter.allow(client):
        raise HTTPException(status_code=429, detail="Integration rate limit exceeded")

    hmac_secret = os.environ.get("MOCHATRADE_HMAC_SECRET")
    legacy_key = os.environ.get("MOCHATRADE_INGEST_KEY")
    if hmac_secret:
        if not all([x_marketbridge_timestamp, x_marketbridge_nonce, x_marketbridge_signature]):
            raise HTTPException(status_code=401, detail="Missing signed-request headers")
        try:
            signed_at = float(x_marketbridge_timestamp)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid signed-request timestamp") from exc
        if abs(time.time() - signed_at) > 10:
            raise HTTPException(status_code=401, detail="Signed request expired")
        body = await request.body()
        headers = SignatureHeaders(x_marketbridge_timestamp, x_marketbridge_nonce, x_marketbridge_signature)
        if not verify_signature(hmac_secret, headers, body):
            raise HTTPException(status_code=401, detail="Invalid request signature")
        if not nonce_store.use_once(x_marketbridge_nonce):
            raise HTTPException(status_code=409, detail="Replay detected")
        return

    if legacy_key:
        if not x_marketbridge_key or not secrets.compare_digest(x_marketbridge_key, legacy_key):
            raise HTTPException(status_code=401, detail="Invalid integration key")
        return

    if client not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail="Configure MOCHATRADE_HMAC_SECRET for remote ingestion")


@app.post("/v1/integrations/mochatrade/market")
async def ingest_mochatrade_mark(
    event: MochatradeMarketEvent,
    request: Request,
    x_marketbridge_key: str | None = Header(default=None),
    x_marketbridge_timestamp: str | None = Header(default=None),
    x_marketbridge_nonce: str | None = Header(default=None),
    x_marketbridge_signature: str | None = Header(default=None),
):
    await _authenticate_integration(
        request, x_marketbridge_key, x_marketbridge_timestamp, x_marketbridge_nonce, x_marketbridge_signature
    )
    if event.event_time.tzinfo is None:
        raise HTTPException(status_code=422, detail="event_time must include a timezone")
    utc_event = event.event_time.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if utc_event > now + timedelta(seconds=5):
        raise HTTPException(status_code=422, detail="event_time cannot be in the future")
    if utc_event < now - timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="event_time is too old")
    if symbol_catalog.get(event.symbol) is None:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    active_subscriptions.touch(event.symbol, "position")
    return {
        "accepted": True,
        "advisory_only": True,
        "mark": pipeline.ingest_mochatrade(
            event.symbol,
            event.mark_price,
            event.event_time,
            context={key: value for key, value in event.model_dump().items() if key not in {"symbol", "mark_price", "event_time"} and value is not None},
        ),
        "decision": next((item for item in pipeline.snapshot()["decisions"] if item["symbol"] == event.symbol), None),
    }


@app.post("/v1/integrations/mochatrade/risk-check")
async def risk_check(
    payload: RiskCheckRequest,
    request: Request,
    x_marketbridge_key: str | None = Header(default=None),
    x_marketbridge_timestamp: str | None = Header(default=None),
    x_marketbridge_nonce: str | None = Header(default=None),
    x_marketbridge_signature: str | None = Header(default=None),
):
    """Return a short-lived advisory order action and Safety Passport."""
    public_synthetic_demo = bool(
        payload.demo_scenario and os.environ.get("MARKETBRIDGE_ENABLE_PUBLIC_DEMO") == "1"
    )
    if not public_synthetic_demo:
        await _authenticate_integration(
            request, x_marketbridge_key, x_marketbridge_timestamp, x_marketbridge_nonce, x_marketbridge_signature
        )
    now = datetime.now(timezone.utc)
    if payload.market.event_time > now + timedelta(seconds=5):
        raise HTTPException(status_code=422, detail="market.event_time cannot be in the future")
    if symbol_catalog.get(payload.symbol) is not None:
        active_subscriptions.touch(payload.symbol, "order")
    started = time.perf_counter()
    try:
        response = risk_gateway.check(payload, pipeline.snapshot(), now=now)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unsupported asset policy") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    observe_risk_check(response, payload.intent.kind.value, time.perf_counter() - started)
    return response


@app.get("/v1/passports/{passport_id}")
def safety_passport(passport_id: str):
    record = risk_gateway.passports.get(passport_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Safety Passport not found")
    verified = PassportStore.verify(record.passport)
    if not verified:
        PASSPORT_VERIFICATION_FAILURE.inc()
    expires_at = datetime.fromisoformat(
        record.passport["claims"]["decision"]["expires_at"].replace("Z", "+00:00")
    )
    return {
        **record.passport,
        "verification_status": "VERIFIED" if verified else "FAILED",
        "expired": datetime.now(timezone.utc) > expires_at,
    }


@app.post("/v1/replay/risk-decision")
def replay_risk_decision(payload: ReplayRequest):
    try:
        result = risk_gateway.replay(payload.passport_id, payload.policy_version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Safety Passport not found") from exc
    if payload.policy_version != "WITHOUT_SAFETY_GATE" and not result["deterministic_parity"]:
        REPLAY_MISMATCH.inc()
    return result


@app.post("/v1/passports/{passport_id}/outcome")
async def record_passport_outcome(
    passport_id: str,
    payload: OutcomeRequest,
    request: Request,
    x_marketbridge_key: str | None = Header(default=None),
    x_marketbridge_timestamp: str | None = Header(default=None),
    x_marketbridge_nonce: str | None = Header(default=None),
    x_marketbridge_signature: str | None = Header(default=None),
):
    await _authenticate_integration(
        request, x_marketbridge_key, x_marketbridge_timestamp, x_marketbridge_nonce, x_marketbridge_signature
    )
    passport = risk_gateway.passports.record_outcome(passport_id, payload.outcome)
    if passport is None:
        raise HTTPException(status_code=404, detail="Safety Passport not found")
    return passport


@app.get("/v1/operator/decision/{scenario_id}")
def operator_decision(
    scenario_id: str,
    symbol: str = Query(default="NVDA", max_length=8),
    second: int = Query(default=24, ge=0, le=60),
):
    if scenario_id not in {item["id"] for item in list_scenarios()} or symbol not in {"NVDA", "TSLA"}:
        raise HTTPException(status_code=404, detail="Unknown scenario or symbol")
    trace = _trace(scenario_id, symbol)
    step = trace["steps"][second]
    return {
        "decision_scope": "DEMO_ADVISORY",
        "data_mode": trace["data_mode"],
        "model_version": trace["model_version"],
        "symbol": symbol,
        "timestamp": step["timestamp"],
        "reference": step["reference"],
        "last_valid": step["last_valid"],
        "status": step["quality"],
        "independent_source_families": step["source_count"],
        "evidence_age_seconds": step["age_seconds"],
        "new_exposure_allowed": step["simulation"]["new_exposure_allowed"],
        "advisory_exposure_multiplier": step["simulation"]["exposure_limit"],
        "assessment": step["assessment"],
        "reasons": step["reasons"],
    }


if (WEB / "_next").is_dir():
    app.mount("/_next", StaticFiles(directory=WEB / "_next"), name="next-assets")


@app.api_route("/{asset_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
def dashboard(asset_path: str):
    if asset_path.startswith(("v1/", ".")):
        raise HTTPException(status_code=404, detail="Not found")
    target = (WEB / (asset_path or "index.html")).resolve()
    if not target.is_relative_to(WEB):
        raise HTTPException(status_code=404, detail="Not found")
    if target.is_file():
        return FileResponse(target)
    directory_index = (target / "index.html").resolve()
    if directory_index.is_relative_to(WEB) and directory_index.is_file():
        return FileResponse(directory_index)
    if asset_path == "":
        return JSONResponse(
            status_code=503,
            content={"detail": "Dashboard not built. Run make build, then restart make serve."},
        )
    raise HTTPException(status_code=404, detail="Not found")
