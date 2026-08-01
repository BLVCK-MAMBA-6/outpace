"""
Authenticated pipeline processing and monitoring task endpoints.
"""

import os
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies.auth import get_current_user
from api.models.schemas import (
    AuthenticatedUser,
    MonitoringEnqueueRequest,
    PipelineRunRequest,
    TaskQueuedResponse,
    TaskStatusResponse,
)
from api.utils.supabase_client import get_supabase_client


router = APIRouter()
supabase = get_supabase_client()


COMPETITOR_TASKS = {
    "general": "monitor_general",
    "pricing": "monitor_pricing",
}

SOURCE_TASKS = {
    "reviews": "monitor_reviews",
    "jobs": "monitor_jobs",
    "news": "monitor_news",
}

SOURCE_TABLES = {
    "reviews": "review_sources",
    "jobs": "job_sources",
    "news": "news_sources",
}

DATABASE_BACKEND = "database"
CELERY_BACKEND = "celery"


def _signal_value(signal_type: Any) -> str:
    """Return the database value for a string enum."""
    return getattr(signal_type, "value", str(signal_type))


def _execution_backend() -> str:
    """Return the configured monitoring task backend."""
    value = os.getenv(
        "MONITORING_EXECUTION_BACKEND",
        DATABASE_BACKEND,
    ).strip().lower()

    if value not in {
        CELERY_BACKEND,
        DATABASE_BACKEND,
    }:
        raise RuntimeError(
            "MONITORING_EXECUTION_BACKEND must be "
            "'celery' or 'database'"
        )

    return value


def _load_celery_task(
    signal_type: str,
) -> Any:
    """Load legacy Celery tasks only when explicitly requested."""
    from workers import tasks as worker_tasks

    task_name = (
        COMPETITOR_TASKS.get(signal_type)
        or SOURCE_TASKS[signal_type]
    )

    return getattr(
        worker_tasks,
        task_name,
    )


def _database_task_response(
    task: dict[str, Any],
) -> dict[str, Any]:
    """Translate a persisted task row to the API contract."""
    state = str(task.get("state") or "PENDING")
    ready = state in {"SUCCESS", "FAILURE"}
    result = task.get("result")

    if result is not None and not isinstance(result, dict):
        result = {"value": result}

    return {
        "task_id": str(task["task_id"]),
        "state": state,
        "ready": ready,
        "successful": (
            state == "SUCCESS"
            if ready
            else None
        ),
        "result": result if state == "SUCCESS" else None,
        "error": (
            str(task["error"])
            if state == "FAILURE" and task.get("error")
            else None
        ),
    }


def _require_owned_competitor(
    competitor_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Return a competitor only when it belongs to this user."""
    try:
        result = (
            supabase.table("competitors")
            .select("id,name,user_id")
            .eq("id", competitor_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify competitor ownership: {error}",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Competitor not found",
        )

    return result.data[0]


def _require_owned_source(
    signal_type: str,
    source_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Return a source only when its competitor belongs to this user."""
    table_name = SOURCE_TABLES[signal_type]

    try:
        result = (
            supabase.table(table_name)
            .select("id,competitor_id")
            .eq("id", source_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify source ownership: {error}",
        ) from error

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Monitoring source not found",
        )

    source = result.data[0]

    _require_owned_competitor(
        competitor_id=str(source["competitor_id"]),
        user_id=user_id,
    )

    return source


@router.post("/run")
def trigger_pipeline(
    request: PipelineRunRequest,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """
    Process the latest two existing snapshots synchronously.

    This endpoint does not collect a new snapshot.
    """
    competitor_id = str(request.competitor_id)
    signal_type = _signal_value(request.signal_type)

    _require_owned_competitor(
        competitor_id=competitor_id,
        user_id=str(current_user.id),
    )

    try:
        from workers.pipeline import run_pipeline

        return run_pipeline(
            competitor_id=competitor_id,
            signal_type=signal_type,
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
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """
    Queue snapshot collection followed by pipeline processing.

    General and pricing require competitor_id.
    Reviews, jobs, and news require source_id.
    """
    signal_type = _signal_value(request.signal_type)
    user_id = str(current_user.id)

    if signal_type in COMPETITOR_TASKS:
        if request.competitor_id is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "competitor_id is required for "
                    f"{signal_type}"
                ),
            )

        target_id = str(request.competitor_id)
        target_type = "competitor"
        _require_owned_competitor(
            competitor_id=target_id,
            user_id=user_id,
        )

    else:
        if request.source_id is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "source_id is required for "
                    f"{signal_type}"
                ),
            )

        target_id = str(request.source_id)
        target_type = "source"
        _require_owned_source(
            signal_type=signal_type,
            source_id=target_id,
            user_id=user_id,
        )

    execution_backend = _execution_backend()

    if execution_backend == DATABASE_BACKEND:
        try:
            existing_result = (
                supabase.table("monitoring_tasks")
                .select("task_id")
                .eq("user_id", user_id)
                .eq("signal_type", signal_type)
                .eq("target_type", target_type)
                .eq("target_id", target_id)
                .eq("execution_backend", DATABASE_BACKEND)
                .in_("state", ["PENDING", "STARTED"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Failed to check pending monitoring tasks: "
                    f"{error}"
                ),
            ) from error

        if existing_result.data:
            return {
                "status": "queued",
                "task_id": str(
                    existing_result.data[0]["task_id"]
                ),
                "signal_type": signal_type,
                "target_id": target_id,
            }

    task_id = str(uuid4())

    tracking_row = {
        "task_id": task_id,
        "user_id": user_id,
        "signal_type": signal_type,
        "target_type": target_type,
        "target_id": target_id,
        "execution_backend": execution_backend,
        "state": "PENDING",
    }

    try:
        tracking_result = (
            supabase.table("monitoring_tasks")
            .insert(tracking_row)
            .execute()
        )

        if not tracking_result.data:
            raise RuntimeError(
                "Database returned no monitoring task"
            )

        if execution_backend == CELERY_BACKEND:
            task_function = _load_celery_task(
                signal_type
            )
            task_function.apply_async(
                args=[target_id],
                task_id=task_id,
            )

    except HTTPException:
        raise
    except Exception as error:
        try:
            (
                supabase.table("monitoring_tasks")
                .delete()
                .eq("task_id", task_id)
                .eq("user_id", user_id)
                .execute()
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=503,
            detail=f"Failed to queue monitoring task: {error}",
        ) from error

    return {
        "status": "queued",
        "task_id": task_id,
        "signal_type": signal_type,
        "target_id": target_id,
    }


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
)
def get_task_status(
    task_id: UUID,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Return a monitoring task only when owned by this user."""
    task_id_value = str(task_id)
    user_id = str(current_user.id)

    try:
        ownership_result = (
            supabase.table("monitoring_tasks")
            .select(
                "task_id,execution_backend,state,"
                "result,error"
            )
            .eq("task_id", task_id_value)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to verify task ownership: {error}",
        ) from error

    if not ownership_result.data:
        raise HTTPException(
            status_code=404,
            detail="Monitoring task not found",
        )

    tracking_task = ownership_result.data[0]

    if (
        tracking_task.get("execution_backend")
        == DATABASE_BACKEND
    ):
        return _database_task_response(tracking_task)

    from celery.result import AsyncResult
    from workers.celery_app import celery_app

    task = AsyncResult(
        task_id_value,
        app=celery_app,
    )

    response = {
        "task_id": task_id_value,
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
