"""Unit tests for market_group_mapping module."""
import pytest
from app.services.market_group_mapping import (
    map_industry_to_market_group,
    MARKET_GROUPS,
    YAHOO_INDUSTRY_TO_MARKET_GROUP,
    MARKET_GROUP_TO_FAMILY,
    FAMILY_BORDER_COLOR,
)


class TestMapIndustryToMarketGroup:
    def test_known_mapping_semiconductors(self):
        assert map_industry_to_market_group("Semiconductors", "Technology") == "Electronic Technology"

    def test_known_mapping_biotechnology(self):
        assert map_industry_to_market_group("Biotechnology") == "Health Technology"

    def test_known_mapping_asset_management(self):
        assert map_industry_to_market_group("Asset Management") == "Finance"

    def test_known_mapping_banks_regional(self):
        assert map_industry_to_market_group("Banks-Regional") == "Banks"

    def test_known_mapping_aerospace_defense(self):
        assert map_industry_to_market_group("Aerospace & Defense") == "Defense"

    def test_none_industry_returns_none(self):
        assert map_industry_to_market_group(None) is None

    def test_none_both_args_returns_none(self):
        assert map_industry_to_market_group(None, None) is None

    def test_empty_string_returns_none(self):
        assert map_industry_to_market_group("") is None

    def test_unknown_industry_returns_none(self):
        assert map_industry_to_market_group("Foobar Industry XYZ") is None

    def test_shell_companies_returns_none(self):
        # Shell Companies / SPACs are intentionally excluded from the heatmap
        assert map_industry_to_market_group("Shell Companies") is None
        assert map_industry_to_market_group("Shell Companies", "Financial Services") is None

    def test_cross_sector_solar_to_renewables(self):
        # Solar is classified as Technology by Yahoo but belongs with Renewables
        assert map_industry_to_market_group("Solar") == "Renewables"
        assert map_industry_to_market_group("Solar", "Technology") == "Renewables"

    def test_cross_sector_internet_content_to_tech_services(self):
        # Internet Content & Information (GICS: Communication Services) → Technology Services
        assert map_industry_to_market_group("Internet Content & Information") == "Technology Services"

    def test_sector_arg_ignored_for_known_industry(self):
        # sector is a reserved arg for Phase 2; for a known industry it has no effect
        result_with = map_industry_to_market_group("Biotechnology", "Healthcare")
        result_without = map_industry_to_market_group("Biotechnology")
        assert result_with == result_without == "Health Technology"

    def test_sector_arg_does_not_enable_unknown_industry(self):
        # Passing a valid sector should not map an unknown industry
        assert map_industry_to_market_group("Unknown Industry", "Technology") is None

    def test_reit_variants_map_to_real_estate(self):
        for industry in ["REIT-Retail", "REIT—Office", "REIT-Residential", "Mortgage REIT"]:
            assert map_industry_to_market_group(industry) == "Real Estate", f"Failed for {industry!r}"

    def test_all_mapped_values_are_in_market_groups(self):
        for industry, group in YAHOO_INDUSTRY_TO_MARKET_GROUP.items():
            assert group in MARKET_GROUPS, (
                f"Industry {industry!r} maps to {group!r} which is not in MARKET_GROUPS"
            )

    def test_all_market_groups_have_family(self):
        for group in MARKET_GROUPS:
            assert group in MARKET_GROUP_TO_FAMILY, f"Market group {group!r} missing from MARKET_GROUP_TO_FAMILY"

    def test_all_families_have_border_color(self):
        families_used = set(MARKET_GROUP_TO_FAMILY.values())
        for family in families_used:
            assert family in FAMILY_BORDER_COLOR, f"Family {family!r} missing from FAMILY_BORDER_COLOR"

    def test_healthcare_plans_maps_to_health_services(self):
        assert map_industry_to_market_group("Healthcare Plans") == "Health Services"

    def test_utilities_renewable_maps_to_renewables(self):
        assert map_industry_to_market_group("Utilities-Renewable") == "Renewables"
        assert map_industry_to_market_group("Utilities—Renewable") == "Renewables"
