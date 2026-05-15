"""Manual classification of stocks into TradingView granular sectors"""

TRADINGVIEW_SECTOR_STOCKS = {
    'Transportation': [
        'UPS', 'FDX', 'UNP', 'CSX', 'NSC', 'JBHT', 'LSTR', 'XPO', 'CHRW', 'EXPD',
        'KNX', 'HUBG', 'WERN', 'SAIA', 'HTLD', 'MRTN', 'ARCB', 'ODFL', 'PTSI', 'SNDR',
        'KSU', 'HTLD', 'SAIA', 'KNX', 'WERN', 'MRTN', 'ARCB', 'SNDR'
    ],
    'Producer Manufacturing': [
        'CAT', 'DE', 'GE', 'HON', 'MMM', 'EMR', 'ROK', 'ITW', 'CMI', 'DOV',
        'PH', 'ETN', 'IR', 'TXT', 'GD', 'LMT', 'RTX', 'NOC', 'BA', 'TDG',
        'PH', 'ETN', 'IR', 'TXT', 'GD'
    ],
    'Health Technology': [
        'JNJ', 'PFE', 'UNH', 'ABT', 'TMO', 'MRK', 'LLY', 'DHR', 'BMY', 'AMGN',
        'GILD', 'REGN', 'BIIB', 'VRTX', 'ILMN', 'ALXN', 'SGEN', 'INCY', 'MYL', 'TEVA',
        'GILD', 'REGN', 'BIIB', 'VRTX', 'ILMN'
    ],
    'Consumer Durables': [
        'AAPL', 'MSFT', 'TSLA', 'NVDA', 'AMD', 'INTC', 'QCOM', 'ADBE', 'CRM', 'ORCL',
        'IBM', 'CSCO', 'ACN', 'SAP', 'NOW', 'SHOP', 'SQ', 'PYPL', 'INTU', 'FISV',
        'HPQ', 'DELL', 'TXN', 'ADI', 'MRVL', 'NXPI', 'AVGO', 'INTC', 'AMD', 'NVDA',
        'MU', 'WDC', 'STX', 'KLAC', 'LRCX'
    ],
    'Retail Trade': [
        'WMT', 'TGT', 'COST', 'AMZN', 'HD', 'LOW', 'M', 'KSS', 'JCP', 'TJX',
        'ROST', 'DLTR', 'BIG', 'TSCO', 'BBY', 'AZO', 'ORLY', 'FIVE', 'KR', 'SYY',
        'ROST', 'DLTR', 'TSCO', 'BBY', 'AZO', 'ORLY', 'FIVE', 'KR', 'CVS'
    ],
    'Commercial Services': [
        'V', 'MA', 'ADP', 'FIS', 'GPN', 'FLT', 'FISV', 'SQ', 'PYPL', 'INTU',
        'ADSK', 'ANSS', 'CTSH', 'MSFT', 'ORCL', 'SAP', 'CRM', 'NOW', 'WDAY', 'ZM',
        'FIS', 'GPN', 'ADSK', 'CTSH', 'IT', 'ACN', 'IBM', 'NOW', 'WDAY', 'ZM', 'DOCU', 'SNOW'
    ],
    'Distribution Services': [
        'UNFI', 'SPTN', 'WM', 'RSG', 'WCN'
    ],
    'Process Industries': [
        'DOW', 'DD', 'PPG', 'LYB', 'AVY', 'EMN', 'FMC', 'IFF', 'NEM', 'FCX',
        'AA', 'ALB', 'CE', 'CF', 'MOS', 'NTR', 'POT', 'SQM', 'VMC', 'MLM',
        'APD', 'EMN', 'FCX', 'NUE', 'RIO', 'BHP', 'VALE', 'AA', 'CENX', 'CLF', 'X', 'NEM', 'GOLD', 'AEM', 'WPM'
    ],
    'Miscellaneous': [
        'BRK.B', 'BAC', 'JPM', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'USB',
        'PNC', 'TFC', 'KEY', 'RF', 'HBAN', 'FITB', 'CFG', 'CMA', 'ZION', 'WAL'
    ]
}

def get_stocks_for_sector(sector: str) -> list:
    """Get stocks for a specific TradingView sector"""
    return TRADINGVIEW_SECTOR_STOCKS.get(sector, [])

def get_all_sectors() -> dict:
    """Get all sectors and their stocks"""
    return TRADINGVIEW_SECTOR_STOCKS
