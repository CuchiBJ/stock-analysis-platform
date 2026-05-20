from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.stock import StockPrice, StockMetrics
from app.data.processors.momentum import (
    calculate_ema, calculate_sma, calculate_rsi,
    calculate_relative_strength,
    calculate_distance_to_ema,
    calculate_relative_volume,
    calculate_performance,
    calculate_adr_percent
)
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class MetricsCalculator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_metrics_for_symbol(self, symbol: str, days: int = 200) -> Optional[StockMetrics]:
        """Calculate and store metrics for a symbol"""
        try:
            # Get price history
            result = await self.db.execute(
                select(StockPrice)
                .where(StockPrice.symbol == symbol.upper())
                .order_by(StockPrice.date.desc())
                .limit(days)
            )
            prices = result.scalars().all()
            
            if len(prices) < 50:  # Need at least 50 days for EMA50
                logger.warning(f"Not enough data for {symbol}: {len(prices)} days")
                return None
            
            # Convert to DataFrame (reverse to chronological order)
            df = pd.DataFrame([{
                'date': p.date,
                'open': p.open,
                'high': p.high,
                'low': p.low,
                'close': p.close,
                'volume': p.volume
            } for p in reversed(prices)])
            
            close_prices = df['close']
            volumes = df['volume']
            
            # Calculate indicators
            ema9 = calculate_ema(close_prices, 9).iloc[-1]
            ema21 = calculate_ema(close_prices, 21).iloc[-1]
            ema20 = calculate_ema(close_prices, 20).iloc[-1]
            ema50 = calculate_ema(close_prices, 50).iloc[-1]
            ema200 = calculate_ema(close_prices, 200).iloc[-1]
            
            # Calculate SMAs
            sma50 = calculate_sma(close_prices, 50).iloc[-1]
            sma150 = calculate_sma(close_prices, 150).iloc[-1]
            sma200 = calculate_sma(close_prices, 200).iloc[-1]
            
            rsi = calculate_rsi(close_prices, 14).iloc[-1]
            
            current_price = close_prices.iloc[-1]
            dist_ema9 = calculate_distance_to_ema(current_price, ema9)
            dist_ema21 = calculate_distance_to_ema(current_price, ema21)
            dist_ema20 = calculate_distance_to_ema(current_price, ema20)
            dist_ema50 = calculate_distance_to_ema(current_price, ema50)
            
            # Calculate 52-week high and low distance
            if len(close_prices) >= 252:
                high_52w = close_prices.tail(252).max()
                low_52w = close_prices.tail(252).min()
            else:
                high_52w = close_prices.max()
                low_52w = close_prices.min()
            dist_high_52w = calculate_distance_to_ema(current_price, high_52w)
            
            # Performance metrics
            perf_1y = calculate_performance(close_prices, 252)
            perf_1w = calculate_performance(close_prices, 5)
            perf_4w = calculate_performance(close_prices, 20)
            perf_13w = calculate_performance(close_prices, 65)
            
            # ADR percentage
            adr_percent = calculate_adr_percent(close_prices, 20) if len(close_prices) >= 20 else 0.0
            
            # Volume metrics
            avg_vol_20d = int(volumes.tail(20).mean())
            avg_vol_10d = int(volumes.tail(10).mean())
            rel_vol = calculate_relative_volume(volumes.iloc[-1], avg_vol_20d)
            
            # Weekly structure metrics (using weekly data from daily prices)
            weekly_tightness = self._calculate_weekly_tightness(df)
            weekly_volatility_contraction = self._calculate_weekly_volatility_contraction(df)
            weekly_trend_quality = self._calculate_weekly_trend_quality(df)
            weeks_in_base = self._calculate_weeks_in_base(df)
            
            # Volatility metrics (calculate before pullback quality for ATR-normalized)
            atr = self._calculate_atr(df)
            current_price = close_prices.iloc[-1]
            atr_percent = (atr / current_price * 100) if current_price > 0 else 0.0
            
            # ATR-normalized positioning (contextual, volatility-aware)
            # distance_to_ema_atr = (price - ema) / atr
            # Positive = above EMA, Negative = below EMA
            # Values in ATR units (e.g., -2.5 = 2.5 ATRs below EMA)
            dist_ema9_atr = (current_price - ema9) / atr if atr > 0 else 0.0
            dist_ema21_atr = (current_price - ema21) / atr if atr > 0 else 0.0
            dist_ema50_atr = (current_price - ema50) / atr if atr > 0 else 0.0
            dist_high_52w_atr = (current_price - high_52w) / atr if atr > 0 and high_52w else 0.0
            
            # Pullback quality metrics (now can use ATR-normalized)
            volume_contraction = self._calculate_volume_contraction(volumes)
            pullback_quality_score = self._calculate_pullback_quality_score(
                dist_ema9, dist_ema21, dist_high_52w, weekly_tightness, 
                volume_contraction, weekly_trend_quality,
                dist_ema9_atr, dist_ema21_atr, dist_high_52w_atr
            )
            setup_quality = self._determine_setup_quality(pullback_quality_score, dist_ema9, dist_ema21)
            
            # Check if metrics already exist for this date
            latest_date = df['date'].iloc[-1]
            existing = await self.db.execute(
                select(StockMetrics).where(
                    and_(
                        StockMetrics.symbol == symbol.upper(),
                        StockMetrics.date == latest_date
                    )
                )
            )
            existing_metrics = existing.scalar_one_or_none()
            
            if existing_metrics:
                # Update existing
                existing_metrics.ema9 = float(ema9)
                existing_metrics.ema21 = float(ema21)
                existing_metrics.ema20 = float(ema20)
                existing_metrics.ema50 = float(ema50)
                existing_metrics.ema200 = float(ema200)
                existing_metrics.rsi = float(rsi)
                existing_metrics.distance_to_ema9 = dist_ema9
                existing_metrics.distance_to_ema21 = dist_ema21
                existing_metrics.distance_to_ema20 = dist_ema20
                existing_metrics.distance_to_ema50 = dist_ema50
                existing_metrics.distance_to_high_52w = dist_high_52w
                existing_metrics.high_52w = float(high_52w)
                existing_metrics.avg_volume_20d = int(avg_vol_20d)
                existing_metrics.relative_volume = rel_vol
                # New indicators
                existing_metrics.sma50 = float(sma50)
                existing_metrics.sma150 = float(sma150)
                existing_metrics.sma200 = float(sma200)
                existing_metrics.perf_1y = float(perf_1y)
                existing_metrics.perf_1w = float(perf_1w)
                existing_metrics.perf_4w = float(perf_4w)
                existing_metrics.perf_13w = float(perf_13w)
                existing_metrics.low_52w = float(low_52w)
                existing_metrics.adr_percent = float(adr_percent)
                existing_metrics.avg_volume_10d = int(avg_vol_10d)
                existing_metrics.current_price = float(current_price)
                # Weekly structure metrics
                existing_metrics.weekly_tightness = weekly_tightness
                existing_metrics.weekly_volatility_contraction = weekly_volatility_contraction
                existing_metrics.weekly_trend_quality = weekly_trend_quality
                existing_metrics.weeks_in_base = weeks_in_base
                # Pullback quality metrics
                existing_metrics.volume_contraction = volume_contraction
                existing_metrics.pullback_quality_score = pullback_quality_score
                existing_metrics.setup_quality = setup_quality
                # Volatility metrics
                existing_metrics.atr = atr
                existing_metrics.atr_percent = atr_percent
                # ATR-normalized positioning
                existing_metrics.distance_to_ema9_atr = dist_ema9_atr
                existing_metrics.distance_to_ema21_atr = dist_ema21_atr
                existing_metrics.distance_to_ema50_atr = dist_ema50_atr
                existing_metrics.distance_to_high_52w_atr = dist_high_52w_atr
                self.db.add(existing_metrics)
            else:
                # Create new
                metrics = StockMetrics(
                    symbol=symbol.upper(),
                    date=latest_date,
                    ema9=float(ema9),
                    ema21=float(ema21),
                    ema20=float(ema20),
                    ema50=float(ema50),
                    ema200=float(ema200),
                    rsi=float(rsi),
                    distance_to_ema9=dist_ema9,
                    distance_to_ema21=dist_ema21,
                    distance_to_ema20=dist_ema20,
                    distance_to_ema50=dist_ema50,
                    distance_to_high_52w=dist_high_52w,
                    avg_volume_20d=int(avg_vol_20d),
                    relative_volume=rel_vol,
                    # New indicators
                    sma50=float(sma50),
                    sma150=float(sma150),
                    sma200=float(sma200),
                    perf_1y=float(perf_1y),
                    perf_1w=float(perf_1w),
                    perf_4w=float(perf_4w),
                    perf_13w=float(perf_13w),
                    low_52w=float(low_52w),
                    adr_percent=float(adr_percent),
                    avg_volume_10d=int(avg_vol_10d),
                    current_price=float(current_price),
                    # Weekly structure metrics
                    weekly_tightness=weekly_tightness,
                    weekly_volatility_contraction=weekly_volatility_contraction,
                    weekly_trend_quality=weekly_trend_quality,
                    weeks_in_base=weeks_in_base,
                    # Pullback quality metrics
                    volume_contraction=volume_contraction,
                    pullback_quality_score=pullback_quality_score,
                    setup_quality=setup_quality,
                    # Volatility metrics
                    atr=atr,
                    atr_percent=atr_percent,
                    # ATR-normalized positioning
                    distance_to_ema9_atr=dist_ema9_atr,
                    distance_to_ema21_atr=dist_ema21_atr,
                    distance_to_ema50_atr=dist_ema50_atr,
                    distance_to_high_52w_atr=dist_high_52w_atr
                )
                self.db.add(metrics)
            
            await self.db.commit()
            logger.info(f"Calculated metrics for {symbol}")
            
            return metrics if not existing_metrics else existing_metrics
            
        except Exception as e:
            logger.error(f"Error calculating metrics for {symbol}: {e}")
            await self.db.rollback()
            raise

    async def calculate_metrics_batch(
        self,
        symbols: List[str],
        days: int = 200
    ) -> int:
        """Calculate metrics for multiple symbols"""
        count = 0
        
        for symbol in symbols:
            try:
                await self.calculate_metrics_for_symbol(symbol, days)
                count += 1
            except Exception as e:
                logger.error(f"Failed to calculate metrics for {symbol}: {e}")
                continue
        
        logger.info(f"Calculated metrics for {count} symbols")
        return count

    async def get_symbols_needing_update(self, hours: int = 24) -> List[str]:
        """Get symbols whose metrics are older than specified hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        result = await self.db.execute(
            select(StockMetrics.symbol)
            .where(StockMetrics.updated_at < cutoff)
            .distinct()
        )
        
        return [row[0] for row in result.all()]

    def _calculate_weekly_tightness(self, df: pd.DataFrame) -> float:
        """Calculate weekly tightness - how tight are weekly closes"""
        if len(df) < 20:  # Need at least 4 weeks
            return 0.0
        
        # Get weekly data (resample to weekly)
        df_weekly = df.copy()
        df_weekly['date'] = pd.to_datetime(df_weekly['date'])
        df_weekly = df_weekly.set_index('date')
        weekly = df_weekly.resample('W').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        if len(weekly) < 4:
            return 0.0
        
        # Calculate tightness based on weekly range relative to price
        weekly['range_pct'] = (weekly['high'] - weekly['low']) / weekly['close'] * 100
        recent_tightness = weekly['range_pct'].tail(4).mean()
        
        # Lower is tighter (better)
        return float(1.0 / (1.0 + recent_tightness)) if recent_tightness > 0 else 0.0

    def _calculate_weekly_volatility_contraction(self, df: pd.DataFrame) -> float:
        """Calculate weekly volatility contraction"""
        if len(df) < 20:
            return 0.0
        
        df_weekly = df.copy()
        df_weekly['date'] = pd.to_datetime(df_weekly['date'])
        df_weekly = df_weekly.set_index('date')
        weekly = df_weekly.resample('W').agg({
            'close': 'last'
        }).dropna()
        
        if len(weekly) < 8:
            return 0.0
        
        # Compare recent volatility to earlier volatility
        recent_vol = weekly['close'].pct_change().tail(4).std()
        earlier_vol = weekly['close'].pct_change().head(4).std()
        
        if earlier_vol == 0:
            return 0.0
        
        # Contraction ratio (recent/earlier)
        return float(1.0 - (recent_vol / earlier_vol))

    def _calculate_weekly_trend_quality(self, df: pd.DataFrame) -> float:
        """Calculate weekly trend quality based on higher highs and higher lows"""
        if len(df) < 20:
            return 0.0
        
        df_weekly = df.copy()
        df_weekly['date'] = pd.to_datetime(df_weekly['date'])
        df_weekly = df_weekly.set_index('date')
        weekly = df_weekly.resample('W').agg({
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        if len(weekly) < 4:
            return 0.0
        
        # Count higher highs and higher lows
        highs = weekly['high'].values
        lows = weekly['low'].values
        
        higher_highs = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        higher_lows = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i-1])
        
        total = len(highs) - 1
        if total == 0:
            return 0.0
        
        return float((higher_highs + higher_lows) / (2 * total))

    def _calculate_weeks_in_base(self, df: pd.DataFrame) -> int:
        """Calculate number of weeks in current consolidation base"""
        if len(df) < 20:
            return 0
        
        df_weekly = df.copy()
        df_weekly['date'] = pd.to_datetime(df_weekly['date'])
        df_weekly = df_weekly.set_index('date')
        weekly = df_weekly.resample('W').agg({
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        if len(weekly) < 4:
            return 0
        
        # Count weeks within recent range
        recent_high = weekly['high'].tail(4).max()
        recent_low = weekly['low'].tail(4).min()
        
        weeks_in_base = 0
        for _, row in weekly.iterrows():
            if recent_low <= row['close'] <= recent_high:
                weeks_in_base += 1
        
        return weeks_in_base

    def _calculate_volume_contraction(self, volumes: pd.Series) -> float:
        """Calculate volume contraction during pullback"""
        if len(volumes) < 10:
            return 0.0
        
        # Compare recent volume to average
        recent_vol = volumes.tail(3).mean()
        avg_vol = volumes.tail(20).mean()
        
        if avg_vol == 0:
            return 0.0
        
        # Contraction ratio
        return float(1.0 - (recent_vol / avg_vol))
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range (ATR)"""
        if len(df) < period + 1:
            return 0.0
        
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        
        # Calculate True Range (TR)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR (simple moving average of TR)
        atr = tr.rolling(window=period).mean().iloc[-1]
        
        return float(atr) if not pd.isna(atr) else 0.0

    def _calculate_pullback_quality_score(
        self,
        dist_ema9: float,
        dist_ema21: float,
        dist_high_52w: float,
        weekly_tightness: float,
        volume_contraction: float,
        weekly_trend_quality: float,
        dist_ema9_atr: float = None,
        dist_ema21_atr: float = None,
        dist_high_52w_atr: float = None
    ) -> float:
        """Calculate overall pullback quality score (0-100) - ATR-normalized"""
        score = 0.0
        
        # Distance to fast EMAs using ATR-normalized positioning (contextual)
        # Ideal: close to EMA9/21 (within 1.5 ATRs, regardless of sign)
        if dist_ema9_atr is not None:
            if abs(dist_ema9_atr) <= 0.5:
                score += 25
            elif abs(dist_ema9_atr) <= 1.0:
                score += 20
            elif abs(dist_ema9_atr) <= 1.5:
                score += 15
            elif abs(dist_ema9_atr) <= 2.0:
                score += 10
        
        if dist_ema21_atr is not None:
            if abs(dist_ema21_atr) <= 0.5:
                score += 20
            elif abs(dist_ema21_atr) <= 1.0:
                score += 15
            elif abs(dist_ema21_atr) <= 1.5:
                score += 10
            elif abs(dist_ema21_atr) <= 2.0:
                score += 5
        
        # Near 52-week high using ATR-normalized positioning (contextual)
        # Ideal: within 2.0 ATRs of high (volatility-aware)
        if dist_high_52w_atr is not None:
            if dist_high_52w_atr >= -1.0:  # Within 1 ATR of high
                score += 20
            elif dist_high_52w_atr >= -2.0:  # Within 2 ATRs of high
                score += 15
            elif dist_high_52w_atr >= -3.0:  # Within 3 ATRs of high
                score += 10
            elif dist_high_52w_atr >= -4.0:  # Within 4 ATRs of high
                score += 5
        
        # Weekly tightness
        score += weekly_tightness * 10
        
        # Volume contraction (drying up on pullback)
        score += max(0, volume_contraction) * 10
        
        # Weekly trend quality (most important factor)
        score += weekly_trend_quality * 25
        
        return min(100.0, max(0.0, score))

    def _determine_setup_quality(self, pullback_score: float, dist_ema9: float, dist_ema21: float) -> str:
        """Determine setup quality category"""
        if pullback_score >= 70 and -3 <= dist_ema9 <= 3:
            return 'excellent'
        elif pullback_score >= 60 and -5 <= dist_ema9 <= 5:
            return 'good'
        elif pullback_score >= 50:
            return 'fair'
        elif pullback_score >= 40:
            return 'developing'
        else:
            return 'poor'
