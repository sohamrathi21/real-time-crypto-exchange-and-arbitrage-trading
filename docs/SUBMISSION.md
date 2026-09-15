# Hackathon submission checklist

The attached participant handbook specifies three deliverables: a public GitHub repository, a working Vercel deployment, and a five-slide PDF/PPTX. It states a 2:30 PM local hard stop on 15 September 2026. The handbook is reference material; no remote publishing or submission is claimed by this file.

## Required team information

- Team name and logo
- Member names, roles, department/year
- Contact email and GitHub IDs
- Final public repository URL
- Final Vercel URL and independently hosted backend URL

## Five-slide content outline

1. **Team introduction:** team identity, members/roles, department/year, contact/GitHub IDs.
2. **Problem:** visible spreads often disappear after bid/ask depth, fees, latency and capital requirements. Audience: students and quantitative market researchers.
3. **USP:** depth-first opportunity intelligence; transparent cost decomposition; executable paper simulation; explicit live/demo/replay labels; explainable confidence. Do not claim trained AI accuracy.
4. **Stack and architecture:** React/TypeScript/Vite/Tailwind/Recharts → FastAPI/WebSockets → quant/risk/paper engines → PostgreSQL/Redis; n8n consumes selected lifecycle events. State that agentic coding tools assisted development.
5. **App and verification:** actual UI screenshots, clickable final URLs, executed test results, safe paper-only scope, and roadmap.

## Deployment

Vercel root: `frontend`. Set `VITE_API_URL` and `VITE_WS_URL` to the separately hosted persistent backend. Verify incognito access. Set backend CORS to the exact frontend origin. The static frontend does not replace FastAPI, Redis, PostgreSQL, or n8n.

Before public hosting, add authentication and account isolation. The local hackathon setup intentionally binds Docker ports to loopback. Never expose the default local shared token or unauthenticated simulation controls publicly.

## Code provenance

Code was authored in this workspace during this task. Do not fabricate commit timestamps, team information, deployment URLs, or test results. Review and commit the work using normal current timestamps before the event's deadline.
