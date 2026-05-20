"""
Real-time Price Service API Endpoints

Endpoints for managing real-time price service:
- Start/stop service
- Get status
- Add/remove symbols
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from app.services.realtime_price_service import get_realtime_price_service

router = APIRouter()


class RealtimeStatusResponse(BaseModel):
    """Response for real-time status"""
    running: bool
    symbols_count: int
    symbols: List[str]
    messages_received: int
    messages_broadcast: int
    last_update: Optional[str]
    connected_clients: int


class StartRealtimeRequest(BaseModel):
    """Request to start real-time service"""
    symbols: Optional[List[str]] = None


@router.post("/start")
async def start_realtime_service(request: StartRealtimeRequest):
    """
    Start real-time price service.
    
    If symbols are provided, subscribes to those symbols.
    If no symbols are provided, subscribes to TIER 1 symbols from Universe Engine.
    """
    try:
        service = get_realtime_price_service()
        await service.start(symbols=request.symbols)
        return {"status": "started", "symbols_count": len(service._symbols)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_realtime_service():
    """Stop real-time price service."""
    try:
        service = get_realtime_price_service()
        await service.stop()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=RealtimeStatusResponse)
async def get_realtime_status():
    """Get current status of real-time price service."""
    try:
        service = get_realtime_price_service()
        status = await service.get_status()
        return RealtimeStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/symbols/add")
async def add_symbols(symbols: List[str]):
    """
    Add symbols to real-time subscription.
    
    Args:
        symbols: List of symbols to add
    """
    try:
        service = get_realtime_price_service()
        await service.add_symbols(symbols)
        return {"status": "added", "count": len(symbols)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/symbols/remove")
async def remove_symbols(symbols: List[str]):
    """
    Remove symbols from real-time subscription.
    
    Args:
        symbols: List of symbols to remove
    """
    try:
        service = get_realtime_price_service()
        await service.remove_symbols(symbols)
        return {"status": "removed", "count": len(symbols)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/symbols/update")
async def update_symbols(symbols: List[str]):
    """
    Update the list of subscribed symbols.
    
    This will restart the service with the new symbol list.
    
    Args:
        symbols: New list of symbols to subscribe to
    """
    try:
        service = get_realtime_price_service()
        await service.update_symbols(symbols)
        return {"status": "updated", "count": len(symbols)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
