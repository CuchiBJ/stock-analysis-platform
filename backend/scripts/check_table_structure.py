"""Check table structure"""
import asyncio
from sqlalchemy import text
from app.core.deps import engine

async def check_tables():
    async with engine.connect() as conn:
        # Check universe_tiers columns
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'universe_tiers' ORDER BY column_name"))
        tiers_columns = [row[0] for row in result]
        print("universe_tiers columns:", tiers_columns)
        
        # Check universe_enrichment columns
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'universe_enrichment' ORDER BY column_name"))
        enrichment_columns = [row[0] for row in result]
        print("universe_enrichment columns:", enrichment_columns)

asyncio.run(check_tables())
