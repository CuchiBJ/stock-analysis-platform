"""Sector mapping service to convert current sectors to TradingView classification"""
from typing import Optional

TRADINGVIEW_SECTORS = {
    # Technology sectors
    'Technology': 'Electronic Technology',
    'Electronic Technology': 'Electronic Technology',
    'Technology Services': 'Technology Services',
    'Communication Services': 'Communications',
    
    # Healthcare sectors
    'Healthcare': 'Health Services',
    'Health Services': 'Health Services',
    'Health Technology': 'Health Technology',
    
    # Financial sectors
    'Financial Services': 'Finance',
    'Finance': 'Finance',
    'Real Estate': 'Finance',
    'ETF': 'ETF',
    
    # Industrial sectors
    'Industrials': 'Industrial Services',
    'Industrial Services': 'Industrial Services',
    'Transportation': 'Transportation',
    'Producer Manufacturing': 'Producer Manufacturing',
    
    # Energy sectors
    'Energy': 'Energy Minerals',
    'Energy Minerals': 'Energy Minerals',
    
    # Materials sectors
    'Basic Materials': 'Non-Energy Minerals',
    'Non-Energy Minerals': 'Non-Energy Minerals',
    
    # Consumer sectors
    'Consumer Cyclical': 'Consumer Services',
    'Consumer Defensive': 'Consumer Non-Durables',
    'Consumer Services': 'Consumer Services',
    'Consumer Non-Durables': 'Consumer Non-Durables',
    'Consumer Durables': 'Consumer Durables',
    'Retail Trade': 'Retail Trade',
    
    # Other sectors
    'Utilities': 'Utilities',
    'Commercial Services': 'Commercial Services',
    'Distribution Services': 'Distribution Services',
    'Process Industries': 'Process Industries',
    'Miscellaneous': 'Miscellaneous',
}

def map_sector_to_tradingview(sector: Optional[str]) -> str:
    """Map a sector name to TradingView classification"""
    if not sector:
        return 'Miscellaneous'
    
    # Direct mapping
    if sector in TRADINGVIEW_SECTORS:
        return TRADINGVIEW_SECTORS[sector]
    
    # Case-insensitive mapping
    for key, value in TRADINGVIEW_SECTORS.items():
        if key.lower() == sector.lower():
            return value
    
    # Default to Miscellaneous for unknown sectors
    return 'Miscellaneous'

def map_sector_list_to_tradingview(sectors: list[str]) -> list[str]:
    """Map a list of sector names to TradingView classification"""
    return [map_sector_to_tradingview(sector) for sector in sectors]
