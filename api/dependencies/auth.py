"""
FastAPI authentication dependencies.
"""

from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from api.models.schemas import AuthenticatedUser
from api.utils.supabase_client import (
    get_supabase_auth_client,
)


bearer_scheme = HTTPBearer(
    auto_error=False
)


def authentication_error() -> HTTPException:
    """Return a consistent Bearer authentication error."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Valid authentication is required",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def get_current_user(
    credentials: (
        HTTPAuthorizationCredentials | None
    ) = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Validate a Supabase access-token JWT."""
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
    ):
        raise authentication_error()

    try:
        response = (
            get_supabase_auth_client()
            .auth.get_user(
                credentials.credentials
            )
        )
    except Exception as error:
        raise authentication_error() from error

    user = response.user

    if user is None:
        raise authentication_error()

    return AuthenticatedUser(
        id=user.id,
        email=user.email,
    )
