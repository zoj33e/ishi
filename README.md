# Ishi

An AI Go teacher. KataGo finds the truth, the Why Engine explains it, Claude narrates it (th / en).
Specs live in `docs/` (start with `CLAUDE.md`).

## Run on this PC

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_engine.ps1   # once: KataGo + nets + .env
powershell -ExecutionPolicy Bypass -File scripts\start.ps1          # API :8000 + web :3000
```

Open http://localhost:3000 and use the browser's "Install app" button to install the PWA.
`-Dev` on `start.ps1` gives hot reload (service worker disabled).

## Develop

```powershell
cd apps\api; uv run pytest; uv run pytest -m engine; uv run ruff check .
cd apps\web; pnpm test; pnpm typecheck; pnpm lint
```

API types for the web app are generated, never hand-written:

```powershell
cd apps\api; uv run python -c "import json; from ishi.main import app; open('openapi.json','w').write(json.dumps(app.openapi(), indent=2))"
cd apps\web; pnpm gen:api
```
