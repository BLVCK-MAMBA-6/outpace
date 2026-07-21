"""
Outpace FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    auth,
    briefs,
    competitors,
    pipeline,
)


app = FastAPI(
    title="Outpace API",
    description=(
        "AI-powered competitive monitoring across websites, "
        "pricing, reviews, jobs, and news."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

app.include_router(
    competitors.router,
    prefix="/competitors",
    tags=["Competitors"],
)

app.include_router(
    briefs.router,
    prefix="/briefs",
    tags=["Briefs"],
)

app.include_router(
    pipeline.router,
    prefix="/pipeline",
    tags=["Pipeline"],
)


@app.get("/", tags=["Health"])
def root():
    """Human-friendly service status."""
    return {
        "status": "ok",
        "service": "outpace-api",
        "version": "0.2.0",
    }


@app.get("/health", tags=["Health"])
def health():
    """Deployment health check."""
    return {
        "status": "healthy",
    }
