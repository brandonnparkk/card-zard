from fastapi import FastAPI

app = FastAPI(title="Card Zard")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
