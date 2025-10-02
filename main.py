from fastapi import FastAPI
from api import webhooks


app = FastAPI(
    title="AI Code Reviewer",
    description="An AI-powered assistant to review your GitHub Pull Requests.",
    version="0.1.0",
)


app.include_router(webhooks.router)


@app.get("/", tags=["Health Check"])
async def read_root():
    return {"status": "ok"}
