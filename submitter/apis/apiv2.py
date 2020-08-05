from flask import Blueprint, abort
from flask.views import MethodView
from webargs import flaskparser, fields, core
from webargs.flaskparser import use_kwargs
from werkzeug.exceptions import HTTPException

from submitter.apis.core import Applications
from submitter.utils import id_generator

v2blueprint = Blueprint("apiv2", __name__)

json_args = {
    "adt": fields.Dict(),
    "url": fields.Str(),
    "params": fields.Dict(),
    "dryrun": fields.Bool(),
}
form_args = {
    "url": fields.Str(),
    "params": fields.Str(),
    "dryrun": fields.Bool(),
}
file_args = {"adt": fields.Field()}


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


class Application(MethodView):
    def get(self, app_id):
        """
        Fetch the application matching the given ID
        """
        return Applications(app_id).get()

    @use_kwargs(json_args, location="json")
    @use_kwargs(file_args, location="files")
    @use_kwargs(form_args, location="form")
    def post(self, app_id, adt=None, url=None, params=None, dryrun=False):
        """
        Create a new application with a given ID
        """
        if not app_id:
            app_id = id_generator()
        return Applications(app_id).create(adt, url, params, dryrun)

    @use_kwargs(json_args, location="json")
    @use_kwargs(file_args, location="files")
    @use_kwargs(form_args, location="form")
    def put(self, app_id, adt=None, url=None, params=None, dryrun=False):
        """
        Update the application matching the given ID
        """

    @use_kwargs({"force": fields.Bool()}, location="form")
    def delete(self, app_id, force=False):
        """
        Delete the application matching the given ID
        """
        return Applications(app_id).delete(force)


class ApplicationStatus(MethodView):
    def get(self, app_id):
        """
        Fetch the deployment status of an application
        """


class ApplicationNodes(MethodView):
    def get(self, app_id):
        """
        Fetch the deployed nodes of an application
        """


class ApplicationServices(MethodView):
    def get(self, app_id):
        """
        Fetch the deployed services of an application
        """


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
