"""Administrator-only process security counters for operational checks."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_active_user
from app.models.user import User, UserRole
from app.services.security_events import security_event_tracker


router = APIRouter(prefix="/operations/security")


@router.get("")
async def security_status(
    user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, object]:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return security_event_tracker.snapshot()
