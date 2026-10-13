# Intelligent Inventory System

A web application that records products and stock movements, learns demand patterns from the
inventory history with machine learning, predicts future demand, and recommends how much stock
to order and how urgent it is.

**Stack:** Python · Flask (REST API) · MongoDB / PyMongo · Pandas · NumPy · Scikit-learn · Joblib ·
Matplotlib · HTML5 / CSS3 / JavaScript · Chart.js · Pytest

## 1. Setup

```bash
git clone https://github.com/julienkigabo54-crypto/System24.git
cd System24
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
```

### Connect MongoDB Atlas
1. In Atlas: **Database → Connect → Drivers**, copy the connection string.
2. **Network Access** → add your current IP address (or `0.0.0.0/0` for a class demo only).
3. Copy `.env.example` to `.env` and fill it in:
   ```
   MONGO_URI=mongodb+srv://<username>:<password>@<cluster-host>/?retryWrites=true&w=majority
   DB_NAME=intelligent_inventory
   ```
   If the password has special characters (`@ : / ?`), URL-encode them. `.env` is git-ignored: never commit it.

(For a local MongoDB use `MONGO_URI=mongodb://localhost:27017`.)

### Load sample data and run
```bash
python seed_data.py     # 15 sample products + 365 days of history (RESETS the database)
python app.py           # open http://localhost:5000
```
Then open **ML Model → Train models**, and the Dashboard, Prediction and Recommendations pages
will show machine-learning results.

> The seed data is **synthetic**. It contains a few deliberate problems (duplicate rows, missing
> values, missing days) so the cleaning step has something to do. Use `--no-dirty` to skip them.
> The seed history ends yesterday, so re-run `python seed_data.py` if you come back days later.

### Run the tests
```bash
pytest -q          # uses an in-memory database (mongomock), never your Atlas data
```

## 2. How it works

| Layer | Where | What it does |
|---|---|---|
| Database | `db.py` | Collections `products`, `inventory_history`, `predictions` (+ `model_runs` log) |
| Products | `services/products.py` | Register, search, update, delete; unique product IDs (unique index) |
| Stock | `services/stock.py` | Atomic stock-in / stock-out; a withdrawal larger than stock is rejected; one history row per product per day |
| Data prep | `services/preprocessing.py` | Quality report; removes duplicates, fixes missing / negative values, fills missing days; builds features |
| ML | `services/ml.py` | Linear Regression (main) + Random Forest (comparison), MAE / MSE / RMSE / R², Joblib saving, retraining, multi-day forecasting |
| Decisions | `services/analysis.py` | Stock requirement, status classification, recommendations, dashboard, analytics |
| Reports | `services/reports.py` | CSV report and Matplotlib chart (PNG) |
| API | `routes/api.py` | JSON REST endpoints under `/api` |
| Pages | `templates/`, `static/` | Landing, Dashboard, Products, Stock In/Out, History, Prediction, Recommendations, Analytics, ML Model |

### The machine-learning model
* One training example = one product on one day; the target is that day's demand (units sold).
* Features: weekday, month, weekend flag, time trend, demand yesterday, 7 days ago, and the 7- and 28-day averages.
* The **newest 20% of dates are held out** and only used to score the models, so the scores measure
  prediction of the future. The final model is then refitted on all data and saved with Joblib.
* To predict several days ahead, the model predicts one day, feeds it back as "yesterday" and repeats.
* **Retraining** (`/api/ml/retrain` or the button on the ML Model page) repeats the process on the
  latest history and shows the old and new scores.
* Linear Regression is used for predictions by default; Random Forest can be selected on the ML Model page.

### Business rules (editable in `config.py`)
* **Target stock** = predicted demand for the window + reorder level (safety buffer)
* **Additional stock required** = target − current stock (never below 0, rounded up)
* **Critical**: out of stock, or stock < demand expected during the supplier lead time (3 days)
* **Low Stock**: stock ≤ reorder level
* **Overstock**: stock > 2 × predicted window demand + reorder level
* **OK**: everything else

## 3. API summary

| Method & path | Purpose |
|---|---|
| `POST/GET /api/products`, `GET/PUT/DELETE /api/products/<id>` | Product management (`?q=` search, `?category=`) |
| `POST /api/stock/in`, `POST /api/stock/out` | Record `{product_id, quantity}` |
| `GET /api/history` | `?product_id=&start=&end=&limit=` |
| `GET /api/data/quality`, `POST /api/data/clean` | Data quality report / cleaning |
| `POST /api/ml/train`, `POST /api/ml/retrain`, `GET /api/ml/status`, `POST /api/ml/active` | Model lifecycle |
| `POST /api/predict` | `{product_id, days, model?}` → daily + total demand, requirement, status (stored) |
| `GET /api/predictions`, `GET /api/recommendations`, `GET /api/alerts`, `GET /api/dashboard` | Decision support |
| `GET /api/analytics/{demand-series,statistics,trends,inventory-value}` | Analytics |
| `GET /api/reports/inventory.csv`, `GET /api/reports/demand-chart/<id>.png` | Reports |

Errors are JSON `{"error": "..."}` with proper status codes (400 invalid input, 404 not found,
409 conflict / insufficient stock / model not trained, 422 not enough data, 503 database unreachable).

## 4. Notes and limitations
* Role-based access control (optional in the brief) is **not** implemented.
* Quantities cannot be edited directly; they change only through stock movements so the history stays correct.
* Deleting a product also deletes its history and predictions.
* Chart.js is loaded from a CDN, so the charts need an internet connection.
* Stock movements are recorded as one aggregated row per product per day (not one row per transaction).
