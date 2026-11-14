"""Application factory: lightweight Flask + standard-library SQLite."""
import json
import os
from pathlib import Path

import click
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from . import db
from .constants import VERSION
from .validation import ConflictError, ValidationError


def create_app(test_config=None):
    root = Path(__file__).resolve().parent.parent
    frontend = Path((test_config or {}).get("FRONTEND_DIST", root.parent / "frontend" / "dist"))
    app = Flask(__name__, instance_path=str(root / "instance"),
                static_folder=str(frontend / "assets"), static_url_path="/assets")
    app.config.from_mapping(DATABASE=str(Path(os.environ.get("CHURN_DB_PATH", root / "instance" / "churn.sqlite")).resolve()),
                            MAX_CONTENT_LENGTH=64 * 1024, TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"])
    if test_config:
        app.config.update(test_config)
    app.config.setdefault('TXB_RESEARCH_ROOT', os.environ.get('TXB_RESEARCH_ROOT'))
    app.config.setdefault('TXB_MODEL_PYTHON', os.environ.get('TXB_MODEL_PYTHON'))
    app.config.setdefault('TXB_SCORING_TIMEOUT_SECONDS', float(os.environ.get('TXB_SCORING_TIMEOUT_SECONDS', '120')))
    app.config.setdefault('TXB_MONTHLY_POPULATION', int(os.environ.get('TXB_MONTHLY_POPULATION', '1000')))
    if not 1 <= app.config['TXB_SCORING_TIMEOUT_SECONDS'] <= 600:
        raise ValueError('TXB_SCORING_TIMEOUT_SECONDS must be between 1 and 600 seconds')
    if type(app.config['TXB_MONTHLY_POPULATION']) is not int or app.config['TXB_MONTHLY_POPULATION'] < 1:
        raise ValueError('TXB_MONTHLY_POPULATION must be a positive server-controlled integer')
    app.teardown_appcontext(db.close_db)
    with app.app_context():
        db.initialise()

    from .api import api
    app.register_blueprint(api)
    from .monthly import MonthlyError

    @app.errorhandler(MonthlyError)
    def monthly_error(error):
        return jsonify(error=dict(code=error.code, message=str(error))), error.status

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
        if not (frontend / "index.html").is_file():
            return jsonify(error=dict(code="frontend_not_built",
                                      message="Build the React frontend with npm run build in frontend/, "
                                              "or use the Vite development server at http://127.0.0.1:5173.")), 503
        return send_from_directory(frontend, "index.html")

    @app.get("/api")
    def api_index():
        return jsonify(name="Corporate attrition backend", version=VERSION,
                       message="React full-stack foundation. Open / for the built dashboard.",
                       endpoints=["/api/health", "/api/months", "/api/summary", "/api/monitoring", "/api/customers"])

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

    @app.cli.command('enrich-batch')
    @click.option('--batch-id',required=True)
    @click.option('--apply', 'do_apply', is_flag=True,help='Commit after full validation; default previews only.')
    @click.option('--replace',is_flag=True,help='Explicitly version a correction to accepted supporting evidence.')
    def enrich_batch_command(batch_id,do_apply,replace):
        """Attach trusted names and recorded cutoff-safe flows to one saved batch."""
        from . import enrichment
        try:
            result = enrichment.apply(batch_id,replace=replace,dry_run=not do_apply)
        except (ValidationError, ConflictError, OSError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(json.dumps(result,indent=2))

    @app.cli.command('load-outcomes')
    @click.option('--batch-id',required=True)
    @click.option('--observed-through',required=True,help='Latest complete observed month, YYYY-MM-DD.')
    @click.option('--apply','do_apply',is_flag=True,help='Publish after validation; default previews only.')
    def load_outcomes_command(batch_id,observed_through,do_apply):
        """Derive mature outcomes from trusted recorded flows for one saved batch."""
        from . import outcomes
        try:
            result=outcomes.publish(batch_id,observed_through,dry_run=not do_apply)
        except (ValidationError,ConflictError,OSError,UnicodeError) as error:
            raise click.ClickException(str(error)) from error
        click.echo(json.dumps(result,indent=2))

    return app
