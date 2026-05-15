from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.core.deps import get_db
from app.models.watchlist import Watchlist
from app.schemas.watchlist import WatchlistCreate, Watchlist as WatchlistSchema

router = APIRouter()


@router.get("/", response_model=List[WatchlistSchema])
async def get_watchlists(db: AsyncSession = Depends(get_db)):
    query = select(Watchlist).where(Watchlist.is_active == True)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=WatchlistSchema)
async def create_watchlist(
    watchlist: WatchlistCreate,
    db: AsyncSession = Depends(get_db)
):
    db_watchlist = Watchlist(
        name=watchlist.name,
        symbols=",".join(watchlist.symbols)
    )
    db.add(db_watchlist)
    await db.commit()
    await db.refresh(db_watchlist)
    
    # Convert back to list for response
    response = WatchlistSchema(
        id=db_watchlist.id,
        name=db_watchlist.name,
        symbols=db_watchlist.symbols.split(","),
        created_at=db_watchlist.created_at,
        is_active=db_watchlist.is_active
    )
    return response
