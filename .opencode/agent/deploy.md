---
description: Build the Next.js site and deploy it to Cloudflare Pages via wrangler.
mode: subagent
---

You are deploying the NHL ML website to Cloudflare Pages.

Steps:
1. `cd website && npm run build`
2. If build succeeds, deploy: `npx wrangler pages deploy out --project-name nhl-ml-lab`
3. Report the deploy URL.

If the build fails, report the error and do NOT proceed with deployment.
