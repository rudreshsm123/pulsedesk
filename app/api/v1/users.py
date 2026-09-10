from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.db import get_db
from app.core.enums import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])

require_agent_or_admin = require_role(UserRole.AGENT, UserRole.ADMIN)


@router.get("/agents", response_model=list[UserOut])
async def list_agents(
    _user=Depends(require_agent_or_admin),
    session: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    # Deliberately narrow (only agents, not the full user table): this exists to
    # populate the assign-ticket picker, not as a general user directory --
    # agent/admin accounts are provisioned out-of-band, customers never need to be
    # listed, and there's no use case here for exposing them.
    agents = await UserRepository(session).list_by_role(UserRole.AGENT.value)
    return [UserOut.model_validate(a) for a in agents]
