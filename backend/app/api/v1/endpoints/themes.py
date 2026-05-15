from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.deps import get_db
from app.schemas.theme import Theme

router = APIRouter()


@router.get("/", response_model=List[Theme])
async def get_themes(db: AsyncSession = Depends(get_db)):
    """Get active market themes"""
    # TODO: Implement theme detection
    return []
