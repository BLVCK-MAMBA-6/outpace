"""
schemas.py — Data Shape Definitions (Pydantic Models)
========================================================
These classes define the "shape" of data flowing in and out of our API.

Why we need this: when a request hits our API (e.g. "add a new competitor"),
FastAPI needs to know what fields to expect, which are required, and what
type each one should be (string, UUID, etc). Pydantic handles all of this
validation automatically — if someone sends bad data, FastAPI rejects it
before our actual logic even runs.

Think of these as "contracts" — they describe what a valid request/response
looks like.
"""

from pydantic import BaseModel, HttpUrl
from typing import Optional
from uuid import UUID
from datetime import datetime


# ------------------------------------------------------------
# COMPETITOR SCHEMAS
# ------------------------------------------------------------

class CompetitorCreate(BaseModel):
    """
    Shape of data required when a user adds a NEW competitor.
    This is what we expect in the request body of a POST request.
    """
    name: str                          # e.g. "Klue"
    website_url: HttpUrl               # e.g. "https://klue.com" — HttpUrl validates it's a real URL format
    pricing_url: Optional[HttpUrl] = None   # optional — user might add this later


class CompetitorResponse(BaseModel):
    """
    Shape of data we SEND BACK after a competitor is created or fetched.
    Includes fields the database generates automatically (id, timestamps)
    that the user never provides themselves.
    """
    id: UUID
    user_id: UUID
    name: str
    website_url: str
    pricing_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        # Allows this model to be built directly from a database row object,
        # not just a plain dictionary.
        from_attributes = True


# ------------------------------------------------------------
# BRIEF SCHEMAS
# ------------------------------------------------------------

class BriefResponse(BaseModel):
    """
    Shape of data we send back when a user views their briefs
    (the AI-synthesized "here's what changed" insights).
    """
    id: UUID
    competitor_id: UUID
    signal_type: str            # 'general', 'pricing', 'reviews', or 'jobs'
    synthesis: dict             # the AI-generated JSON (summary, significance, recommended_action)
    priority: str                # 'low', 'normal', 'high', or 'urgent'
    delivered: bool
    created_at: datetime

    class Config:
        from_attributes = True