"""Intelligent Inventory System - Flask application factory.

Run:  python app.py        (then open http://localhost:5000)
"""
import logging

from flask import Flask, jsonify, request
from pymongo.errors import PyMongoError

from config import Config
from db import init_db
from routes.api import api
from routes.pages import pages
from services.errors import ApiError

log = logging.getLogger(__name__)


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    init_db(app)
    app.register_blueprint(pages)
    app.register_blueprint(api)
    register_error_handlers(app)
    return app


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def api_error(e):
        body = {"error": e.message}
        if e.details:
            body["details"] = e.details
        return jsonify(body), e.status

    @app.errorhandler(PyMongoError)
    def db_error(e):
        log.exception("Database error")
        return jsonify({"error": "The database is unavailable. Check MONGO_URI and your network "
                                 "access list in MongoDB Atlas."}), 503

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Endpoint not found."}), 404
        return "Page not found", 404

    @app.errorhandler(405)
    def not_allowed(e):
        return jsonify({"error": "Method not allowed for this endpoint."}), 405

    @app.errorhandler(Exception)
    def unexpected(e):
        if getattr(e, "code", None) and 400 <= e.code < 500:  # normal HTTP errors from Flask
            return jsonify({"error": getattr(e, "description", "Bad request.")}), e.code
        log.exception("Unhandled error")
        return jsonify({"error": "Unexpected server error."}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="0.0.0.0", port=5000, debug=True)
