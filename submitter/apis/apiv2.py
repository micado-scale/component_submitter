from flask import Blueprint
from flask_restx import Api, Resource


v2blueprint = Blueprint("apiv2", __name__)
api = Api(
    app=v2blueprint,
    title="MiCADO Submitter REST API",
    version="2.0",
    description="An API for applications in MiCADO",
)


@api.route("/application/")
@api.response(500, "Internal Error: Submitter Engine")
class ApplicationList(Resource):
    @api.doc("list_applications")
    def get(self):
        """
        Return a list of deployed applications
        """

    @api.doc("create_application")
    def post(self, file=None, input=None, params=None):
        """
        Create a new application with a generated ID
        """


@api.route("/application/<app_id>/")
@api.param("app_id", "The application identifier")
@api.response(404, "Application not found")
class Application(Resource):
    @api.doc("get_application")
    def get(self, app_id):
        """
        Fetch the application matching the given ID
        """

    def post(self, app_id, file=None, input=None, params=None):
        """
        Create a new application with a given ID
        """

    def put(self, app_id, file=None, input=None, params=None):
        """
        Update the application matching the given ID
        """

    def delete(self, app_id):
        """
        Delete the application matching the given ID
        """


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
