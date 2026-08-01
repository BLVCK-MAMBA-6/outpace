"""
Authenticated per-user weekly digest preference endpoints.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from api.dependencies.auth import get_current_user
from api.models.schemas import (
    AuthenticatedUser,
    DigestPreferenceResponse,
    DigestPreferenceUpdate,
)
from api.utils.supabase_client import get_supabase_client


router = APIRouter()


def verified_delivery_email(
    current_user: AuthenticatedUser,
) -> str:
    """Return the verified Supabase Auth email."""
    email = (
        current_user.email or ""
    ).strip().lower()

    if (
        "@" not in email
        or email.startswith("@")
        or email.endswith("@")
        or " " in email
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "A verified login email is required "
                "for digest delivery"
            ),
        )

    return email


def load_preference(
    user_id: str,
) -> dict[str, Any] | None:
    """Load one user-owned preference row."""
    result = (
        get_supabase_client()
        .table("digest_preferences")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        return None

    return result.data[0]


@router.get(
    "/",
    response_model=DigestPreferenceResponse,
)
def get_digest_preference(
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Return the current user's stored or safe default setting."""
    email = verified_delivery_email(
        current_user
    )
    user_id = str(current_user.id)

    try:
        preference = load_preference(
            user_id
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to retrieve digest preference"
            ),
        ) from error

    if preference is not None:
        return preference

    return {
        "user_id": user_id,
        "enabled": False,
        "delivery_email": email,
        "frequency": "weekly",
        "last_sent_at": None,
        "created_at": None,
        "updated_at": None,
    }


@router.patch(
    "/",
    response_model=DigestPreferenceResponse,
)
def update_digest_preference(
    request: DigestPreferenceUpdate,
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Save the setting using the verified login email."""
    email = verified_delivery_email(
        current_user
    )
    user_id = str(current_user.id)
    updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    record = {
        "user_id": user_id,
        "enabled": request.enabled,
        "delivery_email": email,
        "frequency": "weekly",
        "updated_at": updated_at,
    }

    try:
        result = (
            get_supabase_client()
            .table("digest_preferences")
            .upsert(
                record,
                on_conflict="user_id",
            )
            .execute()
        )

        if result.data:
            return result.data[0]

        preference = load_preference(
            user_id
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to save digest preference"
            ),
        ) from error

    if preference is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Digest preference was not saved"
            ),
        )

    return preference
