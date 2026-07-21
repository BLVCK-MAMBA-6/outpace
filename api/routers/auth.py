"""
Supabase passwordless authentication endpoints.
"""

import os

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from api.dependencies.auth import get_current_user
from api.models.schemas import (
    AuthenticatedUser,
    MagicLinkRequest,
    MagicLinkResponse,
)
from api.utils.supabase_client import (
    get_supabase_auth_client,
)


router = APIRouter()


def normalize_email(email: str) -> str:
    """Apply basic email validation without extra dependencies."""
    normalized = email.strip().lower()

    if (
        "@" not in normalized
        or normalized.startswith("@")
        or normalized.endswith("@")
        or " " in normalized
    ):
        raise HTTPException(
            status_code=422,
            detail="A valid email address is required",
        )

    return normalized


@router.post(
    "/magic-link",
    response_model=MagicLinkResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_magic_link(
    request: MagicLinkRequest,
):
    """
    Request a Supabase magic link.

    The response is deliberately generic so it does not reveal
    whether an email address already has an account.
    """
    email = normalize_email(
        request.email
    )

    credentials = {
        "email": email,
        "options": {
            "should_create_user": True,
        },
    }

    redirect_url = os.getenv(
        "SUPABASE_AUTH_REDIRECT_URL"
    )

    if redirect_url:
        credentials["options"][
            "email_redirect_to"
        ] = redirect_url

    try:
        (
            get_supabase_auth_client()
            .auth.sign_in_with_otp(
                credentials
            )
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Supabase could not send the "
                "authentication email"
            ),
        ) from error

    return {
        "message": (
            "If the address can receive authentication "
            "emails, a sign-in link has been sent."
        )
    }


@router.get(
    "/me",
    response_model=AuthenticatedUser,
)
def get_me(
    current_user: AuthenticatedUser = Depends(
        get_current_user
    ),
):
    """Return the authenticated Supabase user."""
    return current_user
