"""Unit tests for batch_transition_scanner.

Full DB integration test deferred (this repo lacks an async DB fixture).
Tests target the public surface: dataclass shape and module exports.
"""
from app.services.batch_transition_scanner import (
    BatchTransitionScanner,
    ScanStats,
)


class TestScanStatsDataclass:
    def test_fields_present(self):
        stats = ScanStats(
            as_of_date="2026-05-26",
            scanned=10,
            non_stable_detected=3,
            recorded=3,
            errors=0,
            duration_sec=1.5,
        )
        assert stats.as_of_date == "2026-05-26"
        assert stats.scanned == 10
        assert stats.non_stable_detected == 3
        assert stats.recorded == 3
        assert stats.errors == 0
        assert stats.duration_sec == 1.5

    def test_as_of_date_can_be_none(self):
        stats = ScanStats(
            as_of_date=None, scanned=0, non_stable_detected=0,
            recorded=0, errors=0, duration_sec=0.0,
        )
        assert stats.as_of_date is None


class TestScannerExport:
    def test_scanner_class_exists_and_constructs(self):
        # Doesn't connect to DB — just confirms the class shape
        sentinel_db = object()
        scanner = BatchTransitionScanner(sentinel_db)  # type: ignore[arg-type]
        assert scanner.db is sentinel_db

    def test_scan_universe_method_is_async(self):
        import inspect
        assert inspect.iscoroutinefunction(BatchTransitionScanner.scan_universe)
