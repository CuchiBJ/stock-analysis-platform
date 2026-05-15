from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict, Any
from app.core.deps import get_db
from app.services.scanner_service import ScannerService
from app.schemas.scanner import ScannerFilter

router = APIRouter()


class ScannerRequest(BaseModel):
    filter: ScannerFilter
    limit: int = 50


@router.post("/run")
async def run_scan(request: ScannerRequest, db: AsyncSession = Depends(get_db)):
    """Run scanner with custom filters"""
    try:
        scanner_service = ScannerService(db)
        results = await scanner_service.run_scan(request.filter)
        return results[:request.limit]
    except Exception as e:
        import traceback
        print(f"Error in run_scan: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick")
async def run_quick_scan(filter: Dict[str, Any], limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Run quick scan with preset filters"""
    try:
        scanner_service = ScannerService(db)
        results = await scanner_service.run_quick_scan(filter, limit)
        return results
    except Exception as e:
        import traceback
        print(f"Error in run_quick_scan: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/breakout")
async def get_breakout_stocks(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get stocks breaking out"""
    try:
        scanner_service = ScannerService(db)
        results = await scanner_service.get_breakout_stocks(limit)
        return results
    except Exception as e:
        import traceback
        print(f"Error in get_breakout_stocks: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/near-high")
async def get_near_high_stocks(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get stocks near 52-week high"""
    try:
        scanner_service = ScannerService(db)
        results = await scanner_service.get_near_high_stocks(limit)
        return results
    except Exception as e:
        import traceback
        print(f"Error in get_near_high_stocks: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "results": results,
        "total": len(results)
    }


@router.get("/oversold")
async def get_oversold(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get oversold stocks for potential bounce"""
    service = ScannerService(db)
    results = await service.get_oversold_stocks(limit)
    
    return {
        "results": results,
        "total": len(results)
    }


@router.get("/custom")
async def get_custom_screener(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Custom screener based on user's criteria:
    - Precio > SMA 50
    - Market cap 600M - 200B
    - Perf 1Y > 30%
    - SMA 150 > SMA 200
    - Precio > SMA 150
    - Vol medio 10d > 1M
    - SMA 50 > SMA 150
    - 52W range > 60%
    - Precio > 10 USD
    - Perf 1W < 0%
    - Precio > 52W low by 70%
    """
    service = ScannerService(db)
    results = await service.get_custom_screener_stocks(limit)
    
    return {
        "results": results,
        "total": len(results)
    }
