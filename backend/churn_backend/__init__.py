"""Application factory: lightweight Flask + standard-library SQLite."""
import json
import os
from pathlib import Path

import click
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from . import db
from .constants import VERSION
from .validation import ConflictError, ValidationError


def create_app(test_config=None):
    root = Path(__file__).resolve().parent.parent
    frontend = root.parent / "frontend"
    app = Flask(__name__, instance_path=str(root / "instance"),
                static_folder=str(frontend), static_url_path="/assets")
    app.config.from_mapping(DATABASE=str(Path(os.environ.get("CHURN_DB_PATH", root / "instance" / "churn.sqlite")).resolve()),
                            MAX_CONTENT_LENGTH=64 * 1024, TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"])
    if test_config:
        app.config.update(test_config)
    app.teardown_appcontext(db.close_db)
    with app.app_context():
        db.initialise()

    from .api import api
    app.register_blueprint(api)

    @app.before_request
    def local_write_origin():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                return jsonify(error=dict(code="origin_rejected", message="Use the same-origin API or a development proxy.")), 403

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.errorhandler(ValidationError)
    def validation_error(error):
        return jsonify(error=dict(code="validation_failed", message=str(error))), 422

    @app.errorhandler(ConflictError)
    def conflict_error(error):
        return jsonify(error=dict(code="review_conflict", message=str(error))), 409

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=dict(code=error.name.lower().replace(" ", "_"), message=error.description)), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.exception("Unexpected backend error")
        return jsonify(error=dict(code="internal_error", message="The backend encountered an unexpected error.")), 500

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/api")
    def api_index():
        return jsonify(name="Corporate attrition backend", version=VERSION,
                       message="Full-stack foundation. Open / for the dashboard.",
                       endpoints=["/api/health", "/api/months", "/api/summary", "/api/customers"])

    @app.cli.command("init-demo")
    def init_demo():
        """Import the single verified notebook case; existing data is preserved."""
        from .importer import import_demo
        click.echo(json.dumps(import_demo(), indent=2))

    @app.cli.command("import-shap")
    @click.option("--directory", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
    @click.option("--month", required=True, help="YYYY-MM or YYYY-MM-DD month-end")
    @click.option("--customer-master", type=click.Path(exists=True, dir_okay=False, path_type=Path))
    @click.option("--flows", "flows_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
    def import_shap_command(directory, month, customer_master, flows_path):
        """Import one month from a completed, unchanged champion SHAP export."""
        from .importer import import_shap
        try:
            result = import_shap(directory, month, customer_master, flows_path)
        except (ValidationError, OSError, UnicodeError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(json.dumps(result, indent=2))

    return app
