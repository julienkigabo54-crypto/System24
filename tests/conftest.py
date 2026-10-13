import pytest

import seed_data
from app import create_app
from config import TestConfig


def make_app(tmp_path):
    class Cfg(TestConfig):
        MODEL_DIR = tmp_path / "models"

    return create_app(Cfg)


@pytest.fixture
def app(tmp_path):
    """A fresh app with an empty in-memory database (mongomock)."""
    return make_app(tmp_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_app(tmp_path):
    """App with 15 sample products and 150 days of history."""
    application = make_app(tmp_path)
    seed_data.run(application, days=150, dirty=True)
    return application


@pytest.fixture
def seeded(seeded_app):
    return seeded_app.test_client()


def add_product(client, **overrides):
    body = {"product_id": "P1", "name": "Widget", "category": "Tools", "price": 2.5,
            "quantity": 10, "reorder_level": 5}
    body.update(overrides)
    return client.post("/api/products", json=body)
