"""
Pipeline processing and Celery monitoring endpoints.
"""

from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException

from api.models.schemas import (
    MonitoringEnqueueRequest,
    PipelineRunRequest,
    TaskQueuedResponse,
    TaskStatusResponse,
)
from workers.celery_app import celery_app
from workers.pipeline import run_pipeline
from workers.tasks import (
    monitor_general,
    monitor_jobs,
    monitor_news,
    monitor_pricing,
    monitor_reviews,
)


router = APIRouter()


COMPETITOR_TASKS = {
    "general": monitor_general,
    "pricing": monitor_pricing,
}

SOURCE_TASKS = {
    "reviews": monitor_reviews,
    "jobs": monitor_jobs,
    "news": monitor_news,
}


@router.post("/run")
def trigger_pipeline(
    request: PipelineRunRequest,
):
    """
    Process the latest two existing snapshots synchronously.

    This endpoint does not collect a new snapshot.
    """
    try:
        return run_pipeline(
            competitor_id=str(
                request.competitor_id
            ),
            signal_type=request.signal_type,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Pipeline run failed: {error}",
        ) from error


@router.post(
    "/enqueue",
    response_model=TaskQueuedResponse,
    status_code=202,
)
def enqueue_monitoring(
    request: MonitoringEnqueueRequest,
):
    """
    Queue snapshot collection followed by pipeline processing.

    General and pricing require competitor_id.
    Reviews, jobs, and news require source_id.
    """
    if request.signal_type in COMPETITOR_TASKS:
        if request.competitor_id is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "competitor_id is required for "
                    f"{request.signal_type}"
                ),
            )

        task_function = COMPETITOR_TASKS[
            request.signal_type
        ]
        target_id = request.competitor_id

    else:
        if request.source_id is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "source_id is required for "
                    f"{request.signal_type}"
                ),
            )

        task_function = SOURCE_TASKS[
            request.signal_type
        ]
        target_id = request.source_id

    result = task_function.delay(
        str(target_id)
    )

    return {
        "status": "queued",
        "task_id": result.id,
        "signal_type": request.signal_type,
        "target_id": target_id,
    }


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
)
def get_task_status(
    task_id: str,
):
    """Return the current state and compact result of a task."""
    task = AsyncResult(
        task_id,
        app=celery_app,
    )

    response = {
        "task_id": task_id,
        "state": task.state,
        "ready": task.ready(),
        "successful": (
            task.successful()
            if task.ready()
            else None
        ),
        "result": None,
        "error": None,
    }

    if task.successful():
        if isinstance(task.result, dict):
            response["result"] = task.result
        else:
            response["result"] = {
                "value": task.result
            }

    elif task.failed():
        response["error"] = str(task.result)

    return response
