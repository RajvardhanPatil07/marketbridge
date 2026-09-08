"""Read-only demo API and same-origin static dashboard host."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
import secrets
from time import monotonic, sleep

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .scenarios import list_scenarios, run_scenario
from .evaluation import evaluate_all
from .incidents import incident_reconstruction
from .live import get_live_snapshot
from .shadow import LivePipeline, TRACKED_SYMBOLS

ROOT = Path(__file__).resolve().parents[2]
WEB = Path(os.environ.get("MARKETBRIDGE_WEB_DIR", str(ROOT / "apps" / "web" / "out"))).resolve()
pipeline = LivePipeline(ROOT / "artifacts" / "shadow-decisions.jsonl")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    pipeline.start()
    try:
        yield
    finally:
        pipeline.stop()

app = FastAPI(
    title="MarketBridge Demo API",
    version="0.1.0",
    description="Synthetic safety scenarios plus a read-only Yahoo Finance research feed. No execution or validated market forecasts.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type", "X-MarketBridge-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "data_modes": ["SYNTHETIC_TEST", "HISTORICAL_RECONSTRUCTION", "LIVE_RESEARCH", "SHADOW_ORACLE"],
        "web_ready": (WEB / "index.html").exists(),
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


@app.get("/v1/shadow/snapshot")
def shadow_snapshot():
    return pipeline.snapshot()


@app.post("/v1/shadow/refresh")
def refresh_shadow_yahoo():
    return pipeline.refresh_yahoo()


@app.get("/v1/shadow/stream")
def shadow_stream():
    def events():
        generation = -1
        heartbeat = monotonic()
        deadline = monotonic() + 30
        while monotonic() < deadline:
            snapshot = pipeline.snapshot()
            if snapshot["generation"] != generation:
                generation = snapshot["generation"]
                yield f"data:{json.dumps(snapshot, allow_nan=False, separators=(',', ':'))}\n\n"
            elif monotonic() - heartbeat >= 10:
                heartbeat = monotonic()
                yield ":keepalive\n\n"
            sleep(0.1)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})


class MochatradeMarketEvent(BaseModel):
    symbol: str = Field(pattern="^(NVDA|TSLA|QQQ)$")
    mark_price: float = Field(gt=0)
    event_time: datetime


@app.post("/v1/integrations/mochatrade/market")
def ingest_mochatrade_mark(
    event: MochatradeMarketEvent,
    request: Request,
    x_marketbridge_key: str | None = Header(default=None),
):
    expected = os.environ.get("MOCHATRADE_INGEST_KEY")
    if expected and (not x_marketbridge_key or not secrets.compare_digest(x_marketbridge_key, expected)):
        raise HTTPException(status_code=401, detail="Invalid integration key")
    client_host = request.client.host if request.client else None
    if not expected and client_host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(status_code=403, detail="Set MOCHATRADE_INGEST_KEY for remote ingestion")
    if event.event_time.tzinfo is None:
        raise HTTPException(status_code=422, detail="event_time must include a timezone")
    if event.event_time.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(seconds=5):
        raise HTTPException(status_code=422, detail="event_time cannot be in the future")
    if event.symbol not in TRACKED_SYMBOLS:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    return {
        "accepted": True,
        "advisory_only": True,
        "mark": pipeline.ingest_mochatrade(event.symbol, event.mark_price, event.event_time),
    }


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


@app.get("/{asset_path:path}", include_in_schema=False)
def dashboard(asset_path: str):
    if asset_path.startswith(("v1/", ".")):
        raise HTTPException(status_code=404, detail="Not found")
    target = (WEB / (asset_path or "index.html")).resolve()
    if not target.is_relative_to(WEB):
        raise HTTPException(status_code=404, detail="Not found")
    if target.is_file():
        return FileResponse(target)
    if asset_path == "":
        return JSONResponse(
            status_code=503,
            content={"detail": "Dashboard not built. Run make build, then restart make serve."},
        )
    raise HTTPException(status_code=404, detail="Not found")
