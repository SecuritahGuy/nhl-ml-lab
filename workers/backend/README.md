# NHL ML Lab — Cloudflare Worker

Replaces the Python FastAPI backend with a Cloudflare Worker for
serverless edge deployment. Implements the full ML prediction
pipeline in TypeScript.

## Deploy

```bash
npm install
npx wrangler deploy
```

## Dev

```bash
npx wrangler dev
```

## Notes

- Model weights exported from Python (`src/model.json`, 85 features)
- Proxies NHL API endpoints for schedule, rosters, lineups, teams, stats
- CORS enabled for cross-origin frontend access
