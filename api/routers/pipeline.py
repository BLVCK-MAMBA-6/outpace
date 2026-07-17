"""
pipeline.py — Pipeline Trigger Endpoint
==========================================
Exposes the monitoring pipeline (diff -> synthesize -> store brief)
over HTTP, instead of only being runnable from the terminal.

This is what Celery will eventually call on a schedule (Week 4).
For now, it lets you trigger a pipeline run by hitting an endpoint
in /docs instead of typing `python -m workers.pipeline` every time.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from workers.pipeline import run_pipeline


router = APIRouter()


class PipelineRunRequest(BaseModel):
    """Shape of the request body when triggering a pipeline run."""
    competitor_id: str
    signal_type: str = "general"   # 'general', 'pricing', 'reviews', or 'jobs'


@router.post("/run")
def trigger_pipeline(request: PipelineRunRequest):
    """
    Run the diffing -> synthesis -> brief-storage pipeline
    for one competitor and one signal type.

    NOTE: This does NOT scrape a new snapshot first — it compares
    whatever the two most recent snapshots already are. Run the
    scraper separately before calling this if you want fresh data.
    """
    try:
        result = run_pipeline(
            competitor_id=request.competitor_id,
            signal_type=request.signal_type,
        )
    except ValueError as error:
        # e.g. competitor not found
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline run failed: {error}",
        )

    return result