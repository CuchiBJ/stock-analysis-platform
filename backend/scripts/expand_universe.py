#!/usr/bin/env python3
"""
Expand stock universe with NASDAQ Listed + Russell 2000 (IWM holdings).
Adds only tickers not already in the DB, then downloads 1y prices via yfinance.
"""
import asyncio
import sys
import ftplib
import io
import requests
import pandas as pd
import yfinance as yf
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/stock_analysis"
BATCH_SIZE = 100
PERIOD = "1y"

# iShares IWM (Russell 2000) holdings CSV
IWM_HOLDINGS_URL = (
    "https://www.ishares.com/us/products/239726/ishares-russell-2000-etf/"
    "1467271812596.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
)


def fetch_nasdaq_tickers() -> list[str]:
    """Fetch NASDAQ Listed tickers via FTP (nasdaqlisted.txt + otherlisted.txt)."""
    tickers = []
    try:
        logger.info("Connecting to NASDAQ FTP...")
        ftp = ftplib.FTP("ftp.nasdaqtrader.com", timeout=30)
        ftp.login()

        for filename, sym_col, filters in [
            ("nasdaqlisted.txt",  "Symbol",     {"ETF": "N", "Test Issue": "N"}),
            ("otherlisted.txt",   "ACT Symbol", {"ETF": "N", "Test Issue": "N", "Exchange": ["N", "A", "P"]}),
        ]:
            buf = io.BytesIO()
            ftp.retrbinary(f"RETR /SymbolDirectory/{filename}", buf.write)
            buf.seek(0)
            df = pd.read_csv(buf, sep="|")

            for col, val in filters.items():
                if col not in df.columns:
                    continue
                if isinstance(val, list):
                    df = df[df[col].isin(val)]
                else:
                    df = df[df[col] == val]

            if sym_col in df.columns:
                tickers.extend(df[sym_col].dropna().tolist())
                logger.info(f"  {filename}: {len(df)} tickers")

        ftp.quit()
    except Exception as e:
        logger.error(f"NASDAQ FTP error: {e}")

    return tickers


def fetch_russell2000_tickers() -> list[str]:
    """Fetch Russell 2000 tickers from iShares IWM holdings CSV."""
    try:
        logger.info("Fetching Russell 2000 (IWM) holdings...")
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(IWM_HOLDINGS_URL, headers=headers, timeout=30)
        r.raise_for_status()

        # iShares CSV has a header block — find the row that starts the data table
        lines = r.text.splitlines()
        # Try common column names: "Ticker", "Symbol", first col with short all-caps values
        start = next(
            (i for i, l in enumerate(lines)
             if any(l.startswith(col) for col in ["Ticker", "Symbol", "Name,Ticker", "Name,Symbol"])),
            None
        )
        if start is None:
            # Fallback: look for line with header-like content
            start = next((i for i, l in enumerate(lines) if "Ticker" in l or "Symbol" in l), None)
        if start is None:
            logger.warning("Could not find Ticker column in IWM CSV")
            return []

        df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
        ticker_col = next((c for c in ["Ticker", "Symbol"] if c in df.columns), None)
        if not ticker_col:
            logger.warning(f"Columns found: {df.columns.tolist()}")
            return []
        tickers = df[ticker_col].dropna().tolist()
        logger.info(f"  IWM: {len(tickers)} holdings")
        return tickers
    except Exception as e:
        logger.error(f"IWM holdings error: {e}")
        return []


def clean_tickers(raw: list) -> list[str]:
    seen, clean = set(), []
    for t in raw:
        t = str(t).strip().upper().replace(".", "")
        if t and t not in seen and t.isalpha() and 1 <= len(t) <= 5:
            clean.append(t)
            seen.add(t)
    return clean


async def get_existing_symbols(db: AsyncSession) -> set[str]:
    result = await db.execute(text("SELECT symbol FROM stocks"))
    return {row[0] for row in result.fetchall()}


async def insert_new_stocks(db: AsyncSession, tickers: list[str]):
    logger.info(f"Inserting {len(tickers)} new tickers...")
    for symbol in tickers:
        await db.execute(
            text("""
                INSERT INTO stocks (symbol, name, is_active, is_adr)
                VALUES (:s, :s, true, false)
                ON CONFLICT (symbol) DO NOTHING
            """),
            {"s": symbol}
        )
    await db.commit()
    logger.info("Insert complete.")


async def load_prices(db: AsyncSession, tickers: list[str]):
    total = len(tickers)
    ok = fail = 0

    for i in range(0, total, BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        bn = i // BATCH_SIZE + 1
        bt = (total + BATCH_SIZE - 1) // BATCH_SIZE
        logger.info(f"Prices batch {bn}/{bt}: {batch[0]}..{batch[-1]}")

        try:
            data = yf.download(batch, period=PERIOD, auto_adjust=True,
                               progress=False, threads=True)
        except Exception as e:
            logger.error(f"  Download error: {e}")
            fail += len(batch)
            continue

        if data.empty:
            fail += len(batch)
            continue

        multi = isinstance(data.columns, pd.MultiIndex)

        for symbol in batch:
            try:
                hist = data.xs(symbol, axis=1, level=1) if multi else data
                hist = hist.dropna(subset=["Close"])
                if hist.empty:
                    fail += 1
                    continue

                rows = [
                    {
                        "symbol": symbol,
                        "date": d.strftime("%Y-%m-%d"),
                        "open":   float(r["Open"])   if pd.notna(r["Open"])   else None,
                        "high":   float(r["High"])   if pd.notna(r["High"])   else None,
                        "low":    float(r["Low"])    if pd.notna(r["Low"])    else None,
                        "close":  float(r["Close"])  if pd.notna(r["Close"])  else None,
                        "volume": int(r["Volume"])   if pd.notna(r["Volume"]) else None,
                    }
                    for d, r in hist.iterrows()
                ]
                await db.execute(
                    text("""
                        INSERT INTO stock_prices (symbol, date, open, high, low, close, volume)
                        VALUES (:symbol,:date,:open,:high,:low,:close,:volume)
                        ON CONFLICT (symbol, date) DO NOTHING
                    """),
                    rows
                )
                await db.commit()
                ok += 1
            except Exception as e:
                logger.error(f"  {symbol}: {e}")
                await db.rollback()
                fail += 1

        logger.info(f"  Running: {ok} ok, {fail} failed")

    logger.info(f"Prices done: {ok} ok, {fail} failed")


async def main():
    # 1. Fetch tickers from both sources
    nasdaq = fetch_nasdaq_tickers()
    russell = fetch_russell2000_tickers()

    all_tickers = clean_tickers(nasdaq + russell)
    logger.info(f"Total unique tickers from NASDAQ+Russell2000: {len(all_tickers)}")

    engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # 2. Filter to only NEW tickers (not already in DB)
        existing = await get_existing_symbols(db)
        new_tickers = [t for t in all_tickers if t not in existing]
        logger.info(f"New tickers to add: {len(new_tickers)} (skipping {len(existing)} existing)")

        if not new_tickers:
            logger.info("No new tickers — universe already complete.")
        else:
            # 3. Insert new stocks
            await insert_new_stocks(db, new_tickers)
            # 4. Download prices for new tickers only
            await load_prices(db, new_tickers)

    await engine.dispose()
    logger.info("Universe expansion complete. Run metrics calculation next.")


if __name__ == "__main__":
    asyncio.run(main())
