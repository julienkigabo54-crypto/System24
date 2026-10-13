"""HTML pages. They are plain templates; all data comes from the /api routes."""
from flask import Blueprint, render_template

pages = Blueprint("pages", __name__)

PAGES = [
    ("index", "/", "Home"),
    ("dashboard", "/dashboard", "Dashboard"),
    ("products", "/products", "Products"),
    ("stock", "/stock", "Stock In/Out"),
    ("history", "/history", "History"),
    ("predict", "/predict", "Prediction"),
    ("recommendations", "/recommendations", "Recommendations"),
    ("analytics", "/analytics", "Analytics"),
    ("model", "/model", "ML Model"),
]


def _register(key, url):
    def view():
        return render_template(f"{key}.html", pages=PAGES, active=key)
    view.__name__ = f"page_{key}"
    pages.add_url_rule(url, view_func=view)


for _key, _url, _label in PAGES:
    _register(_key, _url)
