from flask import Blueprint, abort
from webargs import flaskparser, core
from werkzeug.exceptions import HTTPException

from .views import Application

v2blueprint = Blueprint("apiv2", __name__)


@flaskparser.parser.error_handler
def webargs_fix(error, req, schema, *, error_status_code, error_headers):
    abort(
        error_status_code or core.DEFAULT_VALIDATION_STATUS, error.messages,
    )


@v2blueprint.errorhandler(Exception)
def unhandled_error_handler(error):
    """Default error handler for unhandled exceptions"""
    return (
        {"message": "Unhandled exception: " + str(error)},
        getattr(error, "code", 500),
    )


@v2blueprint.errorhandler(HTTPException)
def http_error_handler(error):
    """Default error handler for HTTP exceptions"""
    return ({"message": str(error)}, getattr(error, "code", 500))


app_view = Application.as_view("apps_api")
v2blueprint.add_url_rule(
    "/applications/",
    view_func=app_view,
    defaults={"app_id": None},
    methods=["GET", "POST"],
)
v2blueprint.add_url_rule(
    "/applications/<string:app_id>/",
    view_func=app_view,
    methods=["GET", "POST", "PUT", "DELETE"],
)
