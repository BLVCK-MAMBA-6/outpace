"""
Pydantic request and response contracts for the Outpace API.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
)


SignalType = Literal[
    "general",
    "pricing",
    "reviews",
    "jobs",
    "news",
]

BriefPriority = Literal[
    "low",
    "normal",
    "high",
    "urgent",
]


class CompetitorCreate(BaseModel):
    """Create a competitor for the current MVP user."""

    name: str = Field(
        min_length=1,
        max_length=200,
    )
    website_url: HttpUrl
    pricing_url: HttpUrl | None = None


class CompetitorUpdate(BaseModel):
    """Update supplied competitor fields."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    website_url: HttpUrl | None = None
    pricing_url: HttpUrl | None = None


class CompetitorResponse(BaseModel):
    """Competitor returned by the API."""

    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    user_id: UUID
    name: str
    website_url: str
    pricing_url: str | None = None
    created_at: datetime
    updated_at: datetime


class BriefResponse(BaseModel):
    """Stored competitive-intelligence brief."""

    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    competitor_id: UUID
    signal_type: SignalType
    synthesis: dict[str, Any]
    priority: BriefPriority
    delivered: bool
    created_at: datetime


class PipelineRunRequest(BaseModel):
    """Process the two latest stored snapshots."""

    competitor_id: UUID
    signal_type: SignalType = "general"


class MonitoringEnqueueRequest(BaseModel):
    """Queue collection plus pipeline processing."""

    signal_type: SignalType
    competitor_id: UUID | None = None
    source_id: UUID | None = None


class TaskQueuedResponse(BaseModel):
    """Queued Celery task information."""

    status: Literal["queued"]
    task_id: str
    signal_type: SignalType
    target_id: UUID


class TaskStatusResponse(BaseModel):
    """Current state of a Celery task."""

    task_id: str
    state: str
    ready: bool
    successful: bool | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
