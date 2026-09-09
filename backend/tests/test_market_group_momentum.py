from app.services.market_group_momentum import classify_market_group_signals


def test_keeps_sector_leadership_order_and_includes_thematic_groups():
    signals = [
        {"name": "Defense", "relative_strength_4w": 8.0, "relative_strength_5d": 1.2, "acceleration_5d": 0.8},
        {"name": "Energy", "relative_strength_4w": 4.0, "relative_strength_5d": -0.2, "acceleration_5d": -0.6},
        {"name": "Electronic Technology", "relative_strength_4w": 1.0, "relative_strength_5d": 0.5, "acceleration_5d": 0.3},
        {"name": "Banks", "relative_strength_4w": -2.0, "relative_strength_5d": 0.2, "acceleration_5d": 0.4},
    ]

    ranked = classify_market_group_signals(signals)

    assert [item["name"] for item in ranked] == [
        "Defense", "Energy", "Electronic Technology", "Banks"
    ]
    assert [item["weekly_rank"] for item in ranked] == [1, 2, 3, 4]
    assert ranked[0]["status"] == "hot"
    assert ranked[1]["status"] == "cooling"
    assert ranked[3]["status"] == "warming"


def test_summary_explains_both_horizons():
    signal = {
        "name": "Defense",
        "relative_strength_4w": 6.25,
        "relative_strength_5d": 0.75,
        "acceleration_5d": 1.5,
    }

    result = classify_market_group_signals([signal])[0]

    assert "cuatro semanas" in result["summary"]
    assert "cinco días" in result["summary"]
