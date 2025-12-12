from fastapi import FastAPI
from app.api.competitors import router as competitors_router
from app.api.runs import router as runs_router
from app.api.recommendations import router as recommendations_router
from app.api.config import router as config_router
from app.api.push import router as push_router
from app.services.competitor_service import init_db

app = FastAPI(title="Hotel Pricing Agent API")

init_db()

app.include_router(competitors_router)
app.include_router(runs_router)
app.include_router(recommendations_router)
app.include_router(config_router)
app.include_router(push_router)


@app.get("/health")
def health():
    return {"ok": True}
