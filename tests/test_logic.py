"""Unit tests of the business rules (no database needed)."""
import pandas as pd

from config import Config
from services.analysis import classify_status, stock_requirement
from services.preprocessing import clean_history

CFG = {"LEAD_TIME_DAYS": Config.LEAD_TIME_DAYS, "OVERSTOCK_FACTOR": Config.OVERSTOCK_FACTOR}


def test_status_critical():
    assert classify_status(0, 10, 140, 70, CFG) == "Critical"          # out of stock
    assert classify_status(25, 10, 140, 20, CFG) == "Critical"         # < 3 days of demand
    assert classify_status(1, 0, 0, 0, CFG) != "Critical"              # no demand expected


def test_status_low_stock():
    assert classify_status(60, 10, 140, 70, CFG) == "Low Stock"        # at/below reorder level
    assert classify_status(70, 10, 140, 70, CFG) == "Low Stock"


def test_status_ok_and_overstock():
    assert classify_status(150, 10, 140, 70, CFG) == "OK"
    assert classify_status(2 * 140 + 70, 10, 140, 70, CFG) == "OK"     # boundary is not overstock
    assert classify_status(2 * 140 + 71, 10, 140, 70, CFG) == "Overstock"


def test_stock_requirement():
    assert stock_requirement(50, 140, 70) == (210, 160)   # target 210, have 50
    assert stock_requirement(500, 140, 70) == (210, 0)    # never negative
    assert stock_requirement(0, 12.3, 0)[1] == 13          # rounds up to whole units


def _raw(rows):
    return pd.DataFrame(rows, columns=["product_id", "date", "stock_in", "stock_out", "demand", "closing_stock"])


def test_clean_history_handles_duplicates_missing_and_negatives():
    raw = _raw([
        ["P1", "2025-01-01", 0, 5, 5, 50],
        ["P1", "2025-01-01", 0, 5, 5, 50],          # duplicate
        ["P1", "2025-01-02", None, 4, None, None],  # missing values
        ["P1", "2025-01-04", 0, -2, -2, 40],        # negative + a missing day (01-03)
        [None, "2025-01-02", 0, 1, 1, 1],           # no product
        ["P1", "not a date", 0, 1, 1, 1],           # bad date
    ])
    clean = clean_history(raw)
    assert list(clean["date"].dt.strftime("%Y-%m-%d")) == ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]
    assert clean["demand"].tolist() == [5, 4, 0, 0]       # missing demand <- stock_out, gap day = 0, negative = 0
    assert clean["closing_stock"].tolist() == [50, 50, 50, 40]
    assert not clean[["stock_in", "stock_out", "demand", "closing_stock"]].isna().any().any()
