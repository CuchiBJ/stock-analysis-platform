"""
Market group taxonomy for institutional momentum rotation analysis.

Maps Yahoo Finance industry strings to ~25 canonical market groups. Mapping
lives in code (not DB) so changes require code review and are auditable via
git diff. The column stocks.market_group stores only the computed result.
"""

from typing import Optional

MARKET_GROUPS: list[str] = [
    "Electronic Technology",
    "Technology Services",
    "Health Technology",
    "Health Services",
    "Finance",
    "Banks",
    "Insurance",
    "Defense",
    "Industrials",
    "Commercial Services",
    "Transportation",
    "Retail",
    "Consumer Cyclical",
    "Auto",
    "Consumer Staples",
    "Consumer Products",
    "Energy",
    "Renewables",
    "Mining & Metals",
    "Chemicals",
    "Building",
    "Real Estate",
    "Utilities",
    "Media & Telecom",
]

# Maps Yahoo Finance industry strings → canonical market groups.
# Shell Companies is intentionally omitted (returns None — excluded from heatmap).
# Cross-sector decisions are documented inline.
YAHOO_INDUSTRY_TO_MARKET_GROUP: dict[str, str] = {
    # ── Electronic Technology ──────────────────────────────────────────────
    "Semiconductors": "Electronic Technology",
    "Semiconductor Equipment & Materials": "Electronic Technology",
    "Semiconductor Equipment": "Electronic Technology",
    "Electronic Components": "Electronic Technology",
    "Electronic Equipment & Instruments": "Electronic Technology",
    "Electronics & Computer Distribution": "Electronic Technology",
    "Computer Hardware": "Electronic Technology",
    "Technology Hardware, Storage & Peripherals": "Electronic Technology",
    "Technology Hardware": "Electronic Technology",
    "Consumer Electronics": "Electronic Technology",
    "Electronic Manufacturing Services": "Electronic Technology",
    "Technology Distributors": "Electronic Technology",
    "Printed Circuit Board Manufacturing": "Electronic Technology",
    "Communication Equipment": "Electronic Technology",
    "Scientific & Technical Instruments": "Electronic Technology",
    "Electrical Equipment": "Electronic Technology",  # HW-heavy; see Industrials for Electrical Parts

    # ── Technology Services ────────────────────────────────────────────────
    "Software—Application": "Technology Services",
    "Software—Infrastructure": "Technology Services",
    "Software-Application": "Technology Services",
    "Software-Infrastructure": "Technology Services",
    "Software - Application": "Technology Services",
    "Software - Infrastructure": "Technology Services",
    "Information Technology Services": "Technology Services",
    "IT Services": "Technology Services",
    "Cloud Computing": "Technology Services",
    "Computer & Technology": "Technology Services",
    "Consulting Services": "Technology Services",
    # cross-sector: GICS = Communication Services; behavior closer to software
    "Internet Content & Information": "Technology Services",
    "Internet Retail": "Technology Services",  # Amazon, Shopify — platform/tech behavior
    "Data & Analytics": "Technology Services",

    # ── Health Technology ──────────────────────────────────────────────────
    "Biotechnology": "Health Technology",
    "Drug Manufacturers—General": "Health Technology",
    "Drug Manufacturers—Specialty & Generic": "Health Technology",
    "Drug Manufacturers-General": "Health Technology",
    "Drug Manufacturers-Specialty & Generic": "Health Technology",
    "Drug Manufacturers - General": "Health Technology",
    "Drug Manufacturers - Specialty & Generic": "Health Technology",
    "Pharmaceutical Retailers": "Health Technology",
    "Diagnostics & Research": "Health Technology",
    "Medical Devices": "Health Technology",
    "Medical Instruments & Supplies": "Health Technology",
    "Healthcare Technology": "Health Technology",
    "Health Information Services": "Health Technology",
    "Medical Distribution": "Health Technology",
    "Specialty Pharmaceutical": "Health Technology",

    # ── Health Services ────────────────────────────────────────────────────
    "Healthcare Plans": "Health Services",
    "Hospitals": "Health Services",
    "Medical Care Facilities": "Health Services",
    "Medical Facilities": "Health Services",
    "Home Health Care": "Health Services",
    "Pharmacy Benefits Managers": "Health Services",
    "Long-Term Care Facilities": "Health Services",

    # ── Finance ────────────────────────────────────────────────────────────
    "Asset Management": "Finance",
    "Capital Markets": "Finance",
    "Financial Data & Stock Exchanges": "Finance",
    "Credit Services": "Finance",
    "Mortgage Finance": "Finance",
    "Financial Conglomerates": "Finance",
    "Investment Brokerage - National": "Finance",
    "Investment Brokerage - Regional": "Finance",
    "Investment Brokerage": "Finance",
    "Wealth Management": "Finance",
    "Specialty Finance": "Finance",

    # ── Banks ──────────────────────────────────────────────────────────────
    "Banks—Diversified": "Banks",
    "Banks—Regional": "Banks",
    "Banks-Diversified": "Banks",
    "Banks-Regional": "Banks",
    "Banks - Diversified": "Banks",
    "Banks - Regional": "Banks",
    "Savings & Cooperative Banks": "Banks",
    "Bank": "Banks",

    # ── Insurance ──────────────────────────────────────────────────────────
    "Insurance—Life": "Insurance",
    "Insurance—Property & Casualty": "Insurance",
    "Insurance—Specialty": "Insurance",
    "Insurance—Reinsurance": "Insurance",
    "Insurance—Diversified": "Insurance",
    "Insurance-Life": "Insurance",
    "Insurance-Property & Casualty": "Insurance",
    "Insurance-Specialty": "Insurance",
    "Insurance-Reinsurance": "Insurance",
    "Insurance-Diversified": "Insurance",
    "Insurance - Life": "Insurance",
    "Insurance - Property & Casualty": "Insurance",
    "Insurance - Specialty": "Insurance",
    "Insurance - Reinsurance": "Insurance",
    "Insurance - Diversified": "Insurance",
    "Insurance Brokers": "Insurance",
    "Insurance": "Insurance",

    # ── Defense ────────────────────────────────────────────────────────────
    "Aerospace & Defense": "Defense",

    # ── Industrials ────────────────────────────────────────────────────────
    "Specialty Industrial Machinery": "Industrials",
    "Industrial Distribution": "Industrials",
    "Metal Fabrication": "Industrials",
    "Electrical Equipment & Parts": "Industrials",
    "Conglomerates": "Industrials",
    "Tools & Accessories": "Industrials",
    "Farm & Construction Equipment": "Industrials",
    "Farm & Heavy Construction Machinery": "Industrials",
    "Farming & Construction Machinery": "Industrials",
    "Agricultural Inputs": "Industrials",
    "Pollution & Treatment Controls": "Industrials",
    "Waste Management": "Industrials",
    "Infrastructure Operations": "Industrials",
    "Engineering & Construction": "Building",  # re-routed below in Building
    "Industrial Machinery": "Industrials",

    # ── Commercial Services ────────────────────────────────────────────────
    "Staffing & Employment Services": "Commercial Services",
    "Business Services": "Commercial Services",
    "Specialty Business Services": "Commercial Services",
    "Security & Protection Services": "Commercial Services",
    "Rental & Leasing Services": "Commercial Services",
    "Advertising Agencies": "Commercial Services",
    "Marketing Services": "Commercial Services",
    "Office Equipment & Supplies": "Commercial Services",
    "Business Equipment & Supplies": "Commercial Services",
    "Printing": "Commercial Services",
    "Outsourcing Services": "Commercial Services",
    "HR & Benefits Administration": "Commercial Services",
    "Research & Consulting Services": "Commercial Services",
    "Environmental & Waste Services": "Commercial Services",
    "Education & Training Services": "Commercial Services",
    "Personal Services": "Commercial Services",

    # ── Transportation ─────────────────────────────────────────────────────
    "Airlines": "Transportation",
    "Air Freight & Logistics": "Transportation",
    "Shipping & Ports": "Transportation",
    "Railroads": "Transportation",
    "Trucking": "Transportation",
    "Marine Shipping": "Transportation",
    "Transportation Services": "Transportation",
    "Integrated Freight & Logistics": "Transportation",
    "Airport Operators": "Transportation",
    "Airports & Air Services": "Transportation",
    "Courier & Delivery Services": "Transportation",

    # ── Retail ─────────────────────────────────────────────────────────────
    "Specialty Retail": "Retail",
    "Home Improvement Retail": "Retail",
    "Discount Stores": "Retail",
    "Grocery Stores": "Retail",
    "Apparel Retail": "Retail",
    "Pharmacies & Drug Stores": "Retail",
    "Online Retail": "Retail",
    "Department Stores": "Retail",
    "Home Furnishings & Fixtures": "Retail",
    "Lumber & Wood Production": "Retail",
    "Automotive Retail": "Retail",
    "Convenience Stores": "Retail",

    # ── Consumer Cyclical ──────────────────────────────────────────────────
    "Residential Construction": "Consumer Cyclical",
    "Gambling": "Consumer Cyclical",
    "Casinos & Gaming": "Consumer Cyclical",
    "Hotels & Resorts": "Consumer Cyclical",
    "Travel Services": "Consumer Cyclical",
    "Restaurants": "Consumer Cyclical",
    "Fast Food Chains": "Consumer Cyclical",
    "Leisure": "Consumer Cyclical",
    "Recreation": "Consumer Cyclical",
    "Resorts & Casinos": "Consumer Cyclical",
    "Entertainment": "Consumer Cyclical",
    "Lodging": "Consumer Cyclical",
    "Travel & Leisure": "Consumer Cyclical",
    "Cruise Lines": "Consumer Cyclical",
    "Rental Services": "Consumer Cyclical",
    "Furnishings, Fixtures & Appliances": "Consumer Cyclical",

    # ── Auto ───────────────────────────────────────────────────────────────
    "Auto Manufacturers": "Auto",
    "Auto Parts": "Auto",
    "Auto & Truck Dealerships": "Auto",
    "Auto Parts & Equipment": "Auto",
    "Agricultural & Construction Vehicles": "Auto",
    "Recreational Vehicles": "Auto",

    # ── Consumer Staples ───────────────────────────────────────────────────
    "Beverages—Non-Alcoholic": "Consumer Staples",
    "Beverages—Alcoholic": "Consumer Staples",
    "Beverages-Non-Alcoholic": "Consumer Staples",
    "Beverages-Alcoholic": "Consumer Staples",
    "Beverages - Non-Alcoholic": "Consumer Staples",
    "Beverages - Alcoholic": "Consumer Staples",
    "Beverages - Brewers": "Consumer Staples",
    "Beverages - Wineries & Distilleries": "Consumer Staples",
    "Packaged Foods": "Consumer Staples",
    "Tobacco": "Consumer Staples",
    "Household Products": "Consumer Staples",
    "Personal Care Products": "Consumer Staples",
    "Food Distribution": "Consumer Staples",
    "Farm Products": "Consumer Staples",
    "Grocery": "Consumer Staples",
    "Confectioners": "Consumer Staples",
    "Meat Products": "Consumer Staples",
    "Beverages": "Consumer Staples",

    # ── Consumer Products ──────────────────────────────────────────────────
    "Apparel Manufacturing": "Consumer Products",
    "Footwear & Accessories": "Consumer Products",
    "Luxury Goods": "Consumer Products",
    "Toys & Games": "Consumer Products",
    "Sporting & Recreational Goods": "Consumer Products",
    "Electronic Entertainment": "Consumer Products",
    "Household Durables": "Consumer Products",
    "Household & Personal Products": "Consumer Products",
    "Packaging & Containers": "Consumer Products",
    "Paper & Paper Products": "Consumer Products",
    "Textile Manufacturing": "Consumer Products",
    "Cosmetics & Personal Care": "Consumer Products",
    "Personal Products": "Consumer Products",

    # ── Energy ─────────────────────────────────────────────────────────────
    "Oil & Gas E&P": "Energy",
    "Oil & Gas Exploration & Production": "Energy",
    "Oil & Gas Integrated": "Energy",
    "Oil & Gas Midstream": "Energy",
    "Oil & Gas Refining & Marketing": "Energy",
    "Oil & Gas Equipment & Services": "Energy",
    "Oil & Gas Drilling": "Energy",
    "Oil & Gas": "Energy",
    "Energy": "Energy",

    # ── Renewables ─────────────────────────────────────────────────────────
    # cross-sector: Yahoo classifies Solar under Technology; belongs with renewables
    "Solar": "Renewables",
    "Utilities—Renewable": "Renewables",
    "Utilities-Renewable": "Renewables",
    "Utilities - Renewable": "Renewables",
    "Renewable Energy": "Renewables",
    "Wind Energy": "Renewables",

    # ── Mining & Metals ────────────────────────────────────────────────────
    "Gold": "Mining & Metals",
    "Silver": "Mining & Metals",
    "Copper": "Mining & Metals",
    "Other Precious Metals & Mining": "Mining & Metals",
    "Other Industrial Metals & Mining": "Mining & Metals",
    "Steel": "Mining & Metals",
    "Aluminum": "Mining & Metals",
    "Coking Coal": "Mining & Metals",
    "Thermal Coal": "Mining & Metals",
    "Coal": "Mining & Metals",
    "Iron & Steel": "Mining & Metals",
    "Mining": "Mining & Metals",
    "Uranium": "Mining & Metals",

    # ── Chemicals ──────────────────────────────────────────────────────────
    "Specialty Chemicals": "Chemicals",
    "Agricultural Chemicals": "Chemicals",
    "Chemical Manufacturing": "Chemicals",
    "Chemicals": "Chemicals",
    "Basic Materials": "Chemicals",
    "Diversified Chemicals": "Chemicals",
    "Commodity Chemicals": "Chemicals",

    # ── Building ───────────────────────────────────────────────────────────
    "Building Materials": "Building",
    "Building Products & Equipment": "Building",
    "Engineering & Construction": "Building",
    "Real Estate Services": "Building",
    "Real Estate—Development": "Building",
    "Real Estate-Development": "Building",
    "Real Estate - Development": "Building",
    "Construction": "Building",
    "Homebuilding": "Building",

    # ── Real Estate ────────────────────────────────────────────────────────
    "REIT—Retail": "Real Estate",
    "REIT—Office": "Real Estate",
    "REIT—Residential": "Real Estate",
    "REIT—Industrial": "Real Estate",
    "REIT—Healthcare Facilities": "Real Estate",
    "REIT—Hotel & Motel": "Real Estate",
    "REIT—Specialty": "Real Estate",
    "REIT—Mortgage": "Real Estate",
    "REIT—Diversified": "Real Estate",
    "REIT-Retail": "Real Estate",
    "REIT-Office": "Real Estate",
    "REIT-Residential": "Real Estate",
    "REIT-Industrial": "Real Estate",
    "REIT-Healthcare Facilities": "Real Estate",
    "REIT-Hotel & Motel": "Real Estate",
    "REIT-Specialty": "Real Estate",
    "REIT-Mortgage": "Real Estate",
    "REIT-Diversified": "Real Estate",
    "REIT - Retail": "Real Estate",
    "REIT - Office": "Real Estate",
    "REIT - Residential": "Real Estate",
    "REIT - Industrial": "Real Estate",
    "REIT - Healthcare Facilities": "Real Estate",
    "REIT - Hotel & Motel": "Real Estate",
    "REIT - Specialty": "Real Estate",
    "REIT - Mortgage": "Real Estate",
    "REIT - Diversified": "Real Estate",
    "Mortgage REIT": "Real Estate",
    "Real Estate": "Real Estate",

    # ── Utilities ──────────────────────────────────────────────────────────
    "Utilities—Regulated Electric": "Utilities",
    "Utilities—Regulated Gas": "Utilities",
    "Utilities—Regulated Water": "Utilities",
    "Utilities—Diversified": "Utilities",
    "Utilities—Independent Power Producers": "Utilities",
    "Utilities-Regulated Electric": "Utilities",
    "Utilities-Regulated Gas": "Utilities",
    "Utilities-Regulated Water": "Utilities",
    "Utilities-Diversified": "Utilities",
    "Utilities-Independent Power Producers": "Utilities",
    "Utilities - Regulated Electric": "Utilities",
    "Utilities - Regulated Gas": "Utilities",
    "Utilities - Regulated Water": "Utilities",
    "Utilities - Diversified": "Utilities",
    "Utilities - Independent Power Producers": "Utilities",
    "Electric Utilities": "Utilities",
    "Gas Utilities": "Utilities",
    "Water Utilities": "Utilities",
    "Multi-Utilities": "Utilities",

    # ── Media & Telecom ────────────────────────────────────────────────────
    "Telecom Services": "Media & Telecom",
    "Telecommunications Services": "Media & Telecom",
    "Wireless Telecom Services": "Media & Telecom",
    "Media—Diversified": "Media & Telecom",
    "Media-Diversified": "Media & Telecom",
    "Entertainment—Diversified": "Media & Telecom",
    "Entertainment-Diversified": "Media & Telecom",
    "Broadcasting": "Media & Telecom",
    "Publishing": "Media & Telecom",
    "Music": "Media & Telecom",
    "Radio Broadcasting": "Media & Telecom",
    "Film & Television": "Media & Telecom",
    "Pay TV": "Media & Telecom",
    "Cable & Satellite": "Media & Telecom",
    "Electronic Gaming & Multimedia": "Media & Telecom",
    "Streaming": "Media & Telecom",

    # Shell Companies intentionally omitted — SPACs are not operating companies
    # and have no rotation signal value. Stocks with this industry get market_group=NULL.
}

MARKET_GROUP_TO_FAMILY: dict[str, str] = {
    "Electronic Technology": "tech",
    "Technology Services": "tech",
    "Health Technology": "healthcare",
    "Health Services": "healthcare",
    "Finance": "financial",
    "Banks": "financial",
    "Insurance": "financial",
    "Defense": "industrial",
    "Industrials": "industrial",
    "Commercial Services": "industrial",
    "Transportation": "industrial",
    "Retail": "consumer",
    "Consumer Cyclical": "consumer",
    "Auto": "consumer",
    "Consumer Staples": "consumer",
    "Consumer Products": "consumer",
    "Energy": "energy",
    "Renewables": "energy",
    "Mining & Metals": "materials",
    "Chemicals": "materials",
    "Building": "materials",
    "Real Estate": "yield",
    "Utilities": "yield",
    "Media & Telecom": "yield",
}

# Border color per family — Tailwind classes. Source of truth for TS duplicate in SectorHeatmap.tsx.
FAMILY_BORDER_COLOR: dict[str, str] = {
    "tech": "border-l-cyan-500",
    "healthcare": "border-l-pink-500",
    "financial": "border-l-blue-500",
    "industrial": "border-l-amber-500",
    "consumer": "border-l-orange-500",
    "energy": "border-l-red-500",
    "materials": "border-l-stone-500",
    "yield": "border-l-purple-500",
}


def map_industry_to_market_group(
    industry: Optional[str],
    sector: Optional[str] = None,  # reserved for Phase 2 fallback heuristics
) -> Optional[str]:
    """Return the canonical market group for a Yahoo Finance industry string.

    Returns None for None input, unknown industries, and Shell Companies.
    The `sector` argument is accepted for future fallback logic but unused in Phase 1.
    """
    if not industry:
        return None
    return YAHOO_INDUSTRY_TO_MARKET_GROUP.get(industry)
