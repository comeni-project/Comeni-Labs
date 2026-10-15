# Comeni browser application

The React application presents pipeline construction, registry authoring and execution monitoring.
It combines Mendel's build API with Wiener's execution API through one browser origin. Vite serves
local development; the browser image serves compiled files through nginx.

## Run locally

For the complete stack, run `make dev` from the repository root. This installs frontend
dependencies, starts application services and launches Vite. The usual development address is
`http://127.0.0.1:5173`. Set `VITE_HOST_PORT` to choose another port; startup fails if it is occupied.
`make dev` waits for readiness and reports startup failures through `.run/vite.log`.
See [local stack setup](../docs/how-to/development/local-stack.md) for service prerequisites.

When the backend services are already running, start only the frontend from this directory:

```bash
npm ci
npm run dev
```

Node.js and npm are required; the Docker build uses Node 22. `npm ci` installs the locked
frontend dependencies and replaces an existing `node_modules` installation.

## API routing

Browser requests use relative `/api` paths. The development proxy in
[vite.config.ts](vite.config.ts) selects the backend by prefix:

| Prefix | Development target | Owner |
|---|---|---|
| `/api/runs` | `http://localhost` through nginx; WebSocket forwarding enabled. | Wiener run management and live streams. |
| `/api/artifacts` | `http://localhost` through nginx. | Wiener artifact uploads. |
| `/api/wiener` | `http://localhost` through nginx. | Wiener execution settings. |
| Other `/api` requests | `http://localhost:8000` | Mendel. |

Specific Wiener prefixes precede `/api`, because the development proxy matches in insertion
order. Browser routes such as `/forge` stay with the application router.

The proxy reads `WEB_HOST_PORT`, `API_HOST_PORT` and `VITE_HOST_PORT` from the root `.env`,
with exported environment values taking precedence. `make dev` supplies Compose-parsed values;
standalone `npm run dev` uses Vite's dotenv loader. Keep its prefix split aligned with [nginx configuration](../ops/nginx/default.conf).

Wiener requests use its own client because authentication and parameter-refusal responses differ
from Mendel's. The Wiener bearer token is stored in browser local storage and sent as a request
header; it is configured through the UI, rather than embedded in the build.

## Find the owning code

| Location | Responsibility |
|---|---|
| [src/main.tsx](src/main.tsx) | React entry point, query client and browser router. |
| [src/app/](src/app/) | Application shell, routes, navigation and shared URL state. |
| [src/home/](src/home/) | Saved pipeline entry points. |
| [src/build/](src/build/) | Draft building, decisions, review and the conversational builder. |
| [src/forge/](src/forge/) | Registry overview, catalogue, work queue and adaptation review. |
| [src/runs/](src/runs/) | Run board, task details, resource views and live event streams. |
| [src/preferences/](src/preferences/) | Settings overlay, controls and reports. |
| [src/api/](src/api/) | Mendel request wrappers, generated schema types and API hooks. |
| [src/wiener/api/](src/wiener/api/) | Wiener request wrapper and generated schema types. |
| [src/ui/](src/ui/), [src/tokens.css](src/tokens.css), [src/main.css](src/main.css) | Shared controls, terminology and application styling. |

The application route table is [src/app/router.tsx](src/app/router.tsx). It includes compatibility
redirects and retained object-specific deep links. `legacyRoutes` is a separate table used to
exercise retained screens in tests; the application mounts `routes`.

## Generate API types

From the repository root, run:

```bash
make client
```

This imports both application factories to generate `openapi.json` and `openapi.wiener.json`,
then overwrites `src/api/schema.d.ts` and `src/wiener/api/schema.d.ts` with `openapi-typescript`.
Workspace Python dependencies and frontend npm dependencies must be installed. Review the four
file diffs after an API change. Edit request wrappers and hooks by hand; regenerate schema files.

## Verify changes

Run from `frontend/`:

| Check | Command |
|---|---|
| Configured lint rules | `npm run lint` |
| TypeScript project references | `npx tsc -b` |
| Component and helper tests | `npx vitest run` |
| Production compilation and bundle | `npm run build` |
| Inspect an existing bundle locally | `npm run preview` |

`npm run build` runs `tsc -b` before Vite and writes `dist/`. The TypeScript references separate
browser code from Node-based configuration and checks; some tests are excluded from those
projects and still run through Vitest. Preview serves the built output and does not build it.

Tests are colocated with the code as `.test.ts` and `.test.tsx`. Vitest uses `happy-dom` and
[src/setupTests.ts](src/setupTests.ts). That setup supplies synthetic element dimensions so
virtualized lists can render rows without a layout engine. Check that a list renders relevant
rows before asserting a row-count bound. These tests do not establish real-browser geometry;
inspect the app in a browser for layout, scrolling and visual changes.

## Browser image

[Dockerfile](Dockerfile) builds the application and copies `dist/` into nginx's static directory.
Its build context is the repository root so it can also copy `ops/nginx/default.conf`.
Rebuild the web image after changing frontend source or that proxy configuration. Nginx handles
API routing, WebSocket upgrades, artifact upload limits and browser deep-link fallback.

Use the [test index](../tests/README.md) for repository-wide checks and the
[operations index](../ops/README.md) for deployment configuration ownership.
