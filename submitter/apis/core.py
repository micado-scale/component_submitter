from ast import literal_eval
from flask import abort


from submitter import submitter_engine
from submitter import api as flask


SAVE_PATH = "files/templates/"

_engine = submitter_engine.SubmitterEngine()


class Applications:
    """Class to access the Submitter engine object
    """

    def __init__(self):
        """
        Constructor
        """
        self.engine = _engine

    def get(self, app_id=None):
        """Gets application information

        Args:
            app_id (str, optional): App ID. If ommitted, the full app list
                will be returned. Defaults to None.

        Returns:
            dict: Information on the requested application(s)
        """
        if not app_id:
            return self.engine.app_list
        try:
            return self.engine.app_list[app_id]
        except KeyError:
            abort(404, f"Application {app_id} does not exist")

    def create(self, app_id, file=None, url=None, params=None, dryrun=False):
        """Deploys a new application in MiCADO

        Args:
            app_id (str): ID of the application
            file (flask.FileStorage, optional): ADT of the application.
                Defaults to None.
            url (str, optional): URL of the ADT for the application. Defaults
                to None.
            params (str, optional): String repr of the map (dict) of input
                params. Defaults to "{}".
            dryrun (bool, optional): Dry run flag. Defaults to False.
        """
        if self._id_exists(app_id):
            abort(400, "The application ID already exists")
        elif self.engine.app_list:
            abort(400, "Multiple applications are not supported")

        path = _resolve_template_path(app_id, file, url)
        params = _literal_params(params)
        tpl, adaps = self._validate(app_id, path, params, dryrun)
        try:
            self.engine.launch(tpl, adaps, app_id, dryrun)
        except Exception as error:
            abort(500, f"Error while deploying: {error}")

    def _validate(self, app_id, path, params, dryrun):
        """
        Call the engine validate method
        """
        try:
            template, adaptors = self.engine._validate(
                path, dryrun, False, app_id, params
            )
        except Exception as error:
            abort(500, f"Error while validating: {error}")

        return template, adaptors

    def _id_exists(self, app_id):
        """
        Returns True if the app_id exists on the server
        """
        return app_id in self.engine.app_list


def _resolve_template_path(app_id, file, url):
    """
    Saves the template and returns the path, or returns the URL
    """
    path = SAVE_PATH + str(app_id) + ".yaml"
    try:
        file.save(flask.app.root_path + "/" + path)
    except FileNotFoundError:
        abort(500, f"Could not save template to {path}")
    except AttributeError:
        path = url

    if not path:
        abort(400, "No ADT data was included in the request")
    return path


def _literal_params(params):
    """
    Converts string parsed-params into a dicitionary
    """
    params = literal_eval(params) if params else {}
    if not isinstance(params, dict):
        abort(400, "Parsed params are not a valid map (dict)")
    return params
