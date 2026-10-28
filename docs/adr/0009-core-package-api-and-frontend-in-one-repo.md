# One repo: a framework-free core package, a thin FastAPI layer and a React frontend

The domain logic (Deck List parsing, card resolution, Counts, Rules) lives in a Python package, `card_zard`, that doesn't depend on any web framework. A thin FastAPI app in `backend/` exposes it as a JSON API, and a separate React + TypeScript + Vite app in `frontend/` consumes the API. Everything lives in one repository so an API change and the frontend change that uses it land in the same commit. Deck-site importers run on the server, partly because Archidekt blocks cross-origin browser requests.

## Considered Options

- **Server-rendered pages with FastAPI, Jinja and HTMX** would keep everything in Python, but the planned streaming chat and charts are much easier in React.
