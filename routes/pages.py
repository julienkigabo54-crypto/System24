"""HTML pages. They are plain templates; all data comes from the /api routes.

The Dashboard is the start page (there is no separate home page)."""
from flask import Blueprint, redirect, render_template

pages = Blueprint("pages", __name__)

# key (template name), url, name shown in the menu, one-sentence description shown under the title
PAGES = [
    ("dashboard", "/", "Dashboard",
     "See your stock at a glance and find out what needs to be ordered."),
    ("products", "/products", "Products",
     "Add, find, change or delete the products you sell."),
    ("stock", "/stock", "Add or Remove Stock",
     "Record stock you have received, or stock you have sold."),
    ("history", "/history", "Stock History",
     "A daily record of stock added, units sold and stock left."),
    ("predict", "/predict", "Predict Sales",
     "Choose a product and see how many units are likely to sell in the coming days."),
    ("recommendations", "/recommendations", "What to Order",
     "A shopping list that shows what to order, how much, and how urgent it is."),
    ("analytics", "/analytics", "Analytics",
     "Understand what sells, when it sells and how your sales are changing."),
    ("model", "/model", "Prediction Model",
     "The prediction model learns from your past sales. Train it here and check how accurate it is."),
]


def _register(key, url, label, description):
    def view():
        return render_template(f"{key}.html", pages=PAGES, active=key, title=label, subtitle=description)
    view.__name__ = f"page_{key}"
    pages.add_url_rule(url, view_func=view)


for _key, _url, _label, _description in PAGES:
    _register(_key, _url, _label, _description)


@pages.route("/dashboard")
def dashboard_redirect():
    return redirect("/", code=301)
