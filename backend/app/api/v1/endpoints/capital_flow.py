from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.services.capital_flow_service import CapitalFlowService

router = APIRouter()


@router.get("/")
async def get_capital_flows(db: AsyncSession = Depends(get_db)):
    """Get capital flows by sector"""
    try:
        capital_flow_service = CapitalFlowService(db)
        capital_flows = await capital_flow_service.calculate_capital_flows()
        return capital_flows
    except Exception as e:
        import traceback
        print(f"Error in get_capital_flows: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
