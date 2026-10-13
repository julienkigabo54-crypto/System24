"""MongoDB access (PyMongo). Collections:

products          one document per product
inventory_history one document per product per day (stock_in, stock_out, demand, closing_stock)
predictions       every demand prediction that was made
model_runs        log of every model training / retraining run
"""
import logging

from flask import current_app
from pymongo import ASCENDING, MongoClient

log = logging.getLogger(__name__)


def _create_client(config):
    if config.get("USE_MOCK_DB"):
        import mongomock  # imported lazily: only needed for tests

        return mongomock.MongoClient()
    kwargs = {"serverSelectionTimeoutMS": 8000}
    if str(config["MONGO_URI"]).startswith("mongodb+srv") or "mongodb.net" in str(config["MONGO_URI"]):
        try:  # Atlas needs a CA bundle on some systems (notably Windows / macOS Python)
            import certifi

            kwargs["tlsCAFile"] = certifi.where()
        except ImportError:  # pragma: no cover
            pass
    return MongoClient(config["MONGO_URI"], **kwargs)


def ensure_indexes(db):
    db.products.create_index([("product_id", ASCENDING)], unique=True)
    db.inventory_history.create_index([("product_id", ASCENDING), ("date", ASCENDING)])
    db.predictions.create_index([("product_id", ASCENDING), ("created_at", ASCENDING)])


def init_db(app):
    client = _create_client(app.config)
    db = client[app.config["DB_NAME"]]
    app.extensions["mongo_client"] = client
    app.extensions["mongo_db"] = db
    try:
        ensure_indexes(db)
    except Exception as exc:  # connection problems surface as clean 503 errors later
        log.warning("Could not reach MongoDB at startup: %s", exc)
    return db


def get_db():
    return current_app.extensions["mongo_db"]
