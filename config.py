"""Central configuration. Business rules (status thresholds etc.) live here so
they are easy to explain, change and test."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # --- Database -----------------------------------------------------------
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME = os.getenv("DB_NAME", "intelligent_inventory")
    USE_MOCK_DB = os.getenv("USE_MOCK_DB", "0") == "1"  # in-memory DB (tests only)

    # --- Machine learning ---------------------------------------------------
    MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models_saved"))
    DEFAULT_MODEL = "linear_regression"   # the model used for predictions by default
    TEST_FRACTION = 0.2                   # newest 20% of dates form the test set
    MIN_TRAINING_DAYS = 30                # refuse to train with less history than this
    MAX_FORECAST_DAYS = 90

    # --- Inventory business rules ------------------------------------------
    FORECAST_HORIZON_DAYS = 14      # planning window used for status + replenishment
    LEAD_TIME_DAYS = 3              # days a supplier needs to deliver
    OVERSTOCK_FACTOR = 2.0          # overstock if stock > factor * (horizon demand) + reorder level

    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    USE_MOCK_DB = True
    DB_NAME = "inventory_test"
