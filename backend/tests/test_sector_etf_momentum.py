from datetime import date, timedelta

from app.services.sector_etf_momentum import calculate_etf_signal, classify_signals


def _prices(start: float, daily_return: float, sessions: int = 21) -> dict[date, float]:
    first = date(2026, 1, 2)
    return {
        first + timedelta(days=i): start * ((1 + daily_return) ** i)
        for i in range(sessions)
    }


def test_signal_separates_four_week_strength_from_five_day_acceleration():
    spy = _prices(100, 0.001)
    etf = _prices(100, 0.002)
    dates = sorted(etf)

    # Make only the last five sessions meaningfully faster than the prior five.
    anchor = etf[dates[-6]]
    for offset, d in enumerate(dates[-5:], start=1):
        etf[d] = anchor * (1.006 ** offset)

    signal = calculate_etf_signal("XLK", "Technology", etf, spy)

    assert signal is not None
    assert signal["relative_strength_4w"] > 0
    assert signal["relative_strength_5d"] > 0
    assert signal["acceleration_5d"] > 0


def test_signal_requires_twenty_shared_sessions():
    spy = _prices(100, 0.001, sessions=20)
    etf = _prices(100, 0.002, sessions=20)
    assert calculate_etf_signal("XLK", "Technology", etf, spy) is None


def test_classification_uses_rank_and_acceleration():
    signals = [
        {"symbol": "XLK", "relative_strength_4w": 4.0, "relative_strength_5d": 1.0, "acceleration_5d": 0.5},
        {"symbol": "XLE", "relative_strength_4w": 2.0, "relative_strength_5d": -0.2, "acceleration_5d": -0.4},
        {"symbol": "XLF", "relative_strength_4w": -1.0, "relative_strength_5d": 0.4, "acceleration_5d": 0.3},
    ]

    ranked = classify_signals(signals)

    assert [item["weekly_rank"] for item in ranked] == [1, 2, 3]
    assert ranked[0]["status"] == "hot"
    assert ranked[1]["status"] == "cooling"
    assert ranked[2]["status"] == "warming"
    assert "four weeks" in ranked[0]["summary"]
    assert "five days" in ranked[0]["summary"]
