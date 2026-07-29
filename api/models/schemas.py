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

SourceHealthStatus = Literal[
    "unconfigured",
    "disabled",
    "pending",
    "healthy",
    "degraded",
    "blocked",
    "unsupported",
    "failed",
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


class MonitoringSignalStatus(BaseModel):
    """Configuration and collection state for one signal."""

    signal_type: SignalType
    configured: bool
    enabled: bool
    source_id: UUID | None = None
    provider: str | None = None
    source_url: str | None = None
    last_polled_at: datetime | None = None
    latest_snapshot_id: UUID | None = None
    latest_snapshot_at: datetime | None = None
    health_status: SourceHealthStatus
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    consecutive_failures: int = 0


class CompetitorMonitoringResponse(BaseModel):
    """Five-signal monitoring state for one competitor."""

    competitor: CompetitorResponse
    signals: list[MonitoringSignalStatus]


class JobSourceCreate(BaseModel):
    """Configure one supported public careers source."""

    provider: Literal[
        "html",
        "github",
        "ashby",
        "greenhouse",
        "lever",
        "deel",
    ]
    source_url: HttpUrl
    external_source_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9_/-]+$",
    )
    region: Literal["global", "eu"] | None = None
    board_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    job_link_path: str = Field(
        default="/careers/",
        min_length=1,
        max_length=500,
    )
    branch: str = Field(
        default="main",
        min_length=1,
        max_length=200,
    )
    readme_path: str = Field(
        default="README.md",
        min_length=1,
        max_length=500,
    )


class JobSourceDiscoveryRequest(BaseModel):
    """Find a supported public careers provider for confirmation."""

    careers_url: HttpUrl


class JobSourceDiscoveryResponse(BaseModel):
    """One verified source suggestion; never saved automatically."""

    provider: Literal[
        "html",
        "github",
        "ashby",
        "greenhouse",
        "lever",
        "deel",
    ]
    source_url: str
    external_source_id: str | None = None
    region: Literal["global", "eu"] | None = None
    confidence: Literal["high", "medium", "low"]
    detected_by: Literal[
        "direct_url",
        "embedded_reference",
        "verified_company_slug",
        "public_html_fallback",
    ]
    job_count: int | None = None
    requires_confirmation: bool
    message: str
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class NewsSourceCreate(BaseModel):
    """Configure one supported public news or blog source."""

    provider: Literal["html"] = "html"
    source_url: HttpUrl
    article_link_path: str = Field(
        default="/blog/post/",
        min_length=1,
        max_length=500,
    )
    keywords: list[str] = Field(
        default_factory=list,
        max_length=25,
    )
    max_articles: int = Field(
        default=25,
        ge=1,
        le=100,
    )


class MonitoringSourceResponse(BaseModel):
    """Stored source used to queue a monitoring baseline."""

    id: UUID
    competitor_id: UUID
    signal_type: Literal["jobs", "news"]
    provider: str
    source_url: str
    enabled: bool


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
    """Queued monitoring task information."""

    status: Literal["queued"]
    task_id: str
    signal_type: SignalType
    target_id: UUID


class TaskStatusResponse(BaseModel):
    """Current state of a monitoring task."""

    task_id: str
    state: str
    ready: bool
    successful: bool | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

class MagicLinkRequest(BaseModel):
    """Email address requesting passwordless authentication."""

    email: str = Field(
        min_length=3,
        max_length=320,
    )


class MagicLinkResponse(BaseModel):
    """Generic response that prevents account enumeration."""

    message: str


class AuthenticatedUser(BaseModel):
    """Trusted user returned after JWT validation."""

    id: UUID
    email: str | None = None
