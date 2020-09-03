from flask.views import MethodView
from webargs.flaskparser import use_kwargs

from submitter.apis.common import Applications
from submitter.utils import id_generator
from .models import ReqArgs, AppSchema, AppListSchema


class Application(MethodView):
    def get(self, app_id):
        """
        Fetch the application matching the given ID
        """
        if app_id:
            return AppSchema().dump(Applications(app_id).get())
        else:
            return AppListSchema().dump(Applications().get())

    @use_kwargs(ReqArgs.json, location="json")
    @use_kwargs(ReqArgs.file, location="files")
    @use_kwargs(ReqArgs.form, location="form")
    def post(self, app_id, adt=None, url=None, params=None, dryrun=False):
        """
        Create a new application with a given ID
        """
        if not app_id:
            app_id = id_generator()
        return Applications(app_id).create(adt, url, params, dryrun)

    @use_kwargs(ReqArgs.json, location="json")
    @use_kwargs(ReqArgs.file, location="files")
    @use_kwargs(ReqArgs.form, location="form")
    def put(self, app_id, adt=None, url=None, params=None):
        """
        Update the application matching the given ID
        """
        return Applications(app_id).update(adt, url, params)

    @use_kwargs(ReqArgs.force, location="form")
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
