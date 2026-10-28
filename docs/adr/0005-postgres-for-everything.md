# Postgres stores everything, including future vectors

Snapshots, Deck Lists, Share Links and (later) users all live in one Postgres database, accessed through SQLAlchemy 2.0 with Alembic migrations. When retrieval is needed (phase 3), vectors use the `pgvector` extension in the same database instead of a separate vector store. We chose Postgres over SQLite because this is a public multi-user product, and over a dedicated vector database because card data is mostly structured and most "retrieval" is really SQL over card fields. Locally it runs in Docker.

## Considered Options

- **SQLite now, migrate later**: simpler to start, but a guaranteed migration once the app is hosted.
- **A dedicated vector database**: a second system to run and keep in sync, for a feature that may only cover recommendation questions.
