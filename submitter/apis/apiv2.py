from flask import Blueprint, abort
from flask_restx import Api, Resource
from webargs import flaskparser, fields, core
from webargs.flaskparser import use_kwargs
from werkzeug.exceptions import HTTPException

from submitter.apis.core import Applications
from submitter.utils import id_generator

v2blueprint = Blueprint("apiv2", __name__)
api = Api(
    app=v2blueprint,
    title="MiCADO Submitter REST API",
    version="2.0",
    description="An API for applications in MiCADO",
)

apps = Applications()

form_args = {
    "url": fields.Str(),
    "params": fields.Str(),
    "dryrun": fields.Bool(),
}
file_args = {"file": fields.Field()}


@api.errorhandler(HTTPException)
def internal_error_handler(error):
    """Re-raise all HTTPExceptions for Flask errorhandler """
    raise error


@flaskparser.parser.error_handler
def webargs_fix(error, req, schema, *, error_status_code, error_headers):
    abort(
        error_status_code or core.DEFAULT_VALIDATION_STATUS,
        error.messages,
    )


@api.route("/application/")
@api.response(500, "Internal Error: Submitter Engine")
class ApplicationList(Resource):
    @api.doc("list_applications")
    def get(self):
        """
        Return a list of deployed applications
        """
        return apps.get()

    @api.doc("create_application")
    @use_kwargs(file_args, location="files")
    @use_kwargs(form_args, location="form")
    def post(self, file=None, url=None, params=None, dryrun=False):
        """
        Create a new application with a generated ID
        """
        app_id = id_generator()
        return apps.create(app_id, file, url, params, dryrun)


@api.route("/application/<app_id>/")
@api.param("app_id", "The application identifier")
@api.response(404, "Application not found")
class Application(Resource):
    @api.doc("get_application")
    def get(self, app_id):
        """
        Fetch the application matching the given ID
        """
        return apps.get(app_id)

    @use_kwargs(file_args, location="files")
    @use_kwargs(form_args, location="form")
    def post(self, app_id, file=None, url=None, params=None, dryrun=False):
        """
        Create a new application with a given ID
        """
        return apps.create(app_id, file, url, params, dryrun)

    @use_kwargs(file_args, location="files")
    @use_kwargs(form_args, location="form")
    def put(self, app_id, file=None, url=None, params=None, dryrun=False):
        """
        Update the application matching the given ID
        """

    @use_kwargs({"force": fields.Bool()}, location="form")
    def delete(self, app_id, force=False):
        """
        Delete the application matching the given ID
        """
        return apps.delete(app_id, force)


@api.route("/application/<app_id>/status")
@api.param("app_id", "The application identifier")
@api.response(404, "Application not found")
class ApplicationStatus(Resource):
    @api.doc("get_application_status")
    def get(self, app_id):
        """
        Fetch the deployment status of an application
        """


@api.route("/application/<app_id>/nodes")
@api.param("app_id", "The application identifier")
@api.response(404, "Application not found")
class ApplicationNodes(Resource):
    @api.doc("get_application_nodes")
    def get(self, app_id):
        """
        Fetch the deployed nodes of an application
        """


@api.route("/application/<app_id>/services")
@api.param("app_id", "The application identifier")
@api.response(404, "Application not found")
class ApplicationServices(Resource):
    @api.doc("get_application_services")
    def get(self, app_id):
        """
        Fetch the deployed services of an application
        """
