type RiskAction = "ALLOW" | "CAP_LEVERAGE" | "REVIEW" | "BLOCK_NEW_RISK";

type RiskResponse = {
  action: RiskAction;
  passport_id: string;
  expires_at: string;
  requested_leverage: number;
  permitted_leverage: number;
  requested_notional_usd: number;
  permitted_notional_usd: number;
  safe_alternative: {
    available: boolean;
    max_leverage: number;
    max_notional_usd: number;
    message: string;
  };
};

export async function pretradeMarketBridgeCheck(apiBase: string, payload: unknown): Promise<RiskResponse> {
  const response = await fetch(apiBase + "/v1/integrations/mochatrade/risk-check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("MarketBridge risk check failed: " + response.status);
  return response.json() as Promise<RiskResponse>;
}

export function applyRiskDecision(result: RiskResponse, host: {
  disableSubmit: (reason: string) => void;
  setOrderCap: (leverage: number, notionalUsd: number) => void;
  sendToReview: (passportId: string) => void;
  attachPassport: (passportId: string, expiresAt: string) => void;
}) {
  host.attachPassport(result.passport_id, result.expires_at);
  if (result.action === "BLOCK_NEW_RISK") { host.disableSubmit("MarketBridge blocked new risk"); return; }
  if (result.action === "CAP_LEVERAGE") { host.setOrderCap(result.safe_alternative.max_leverage, result.safe_alternative.max_notional_usd); return; }
  if (result.action === "REVIEW") host.sendToReview(result.passport_id);
}