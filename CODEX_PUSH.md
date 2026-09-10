# Push this upgrade with Codex / GitHub write access

Recommended flow:

```bash
git clone https://github.com/RajvardhanPatil07/marketbridge.git
cd marketbridge
git checkout -b feat/marketbridge-v0.2
```

Copy the **contents** of this ZIP into the cloned repository (do not copy a `.git` folder; this ZIP does not contain one), then run:

```bash
git add -A
git status
git commit -m "feat: upgrade MarketBridge live risk and market integrity stack"
git push -u origin feat/marketbridge-v0.2
```

Create the pull request:

```bash
gh pr create \
  --repo RajvardhanPatil07/marketbridge \
  --base main \
  --head feat/marketbridge-v0.2 \
  --title "feat: MarketBridge v0.2 live market integrity upgrade" \
  --body "Adds WebSocket-first live streaming, Alpaca/Hyperliquid adapters, provider+venue lineage, confidence bands, dynamic risk limits, HMAC/replay protection, responsive market UI, Railway/Vercel configs, tests, and security documentation."
```

Before pushing production secrets, read `SECURITY.md`. Never commit `.env` or `.env.local`.
