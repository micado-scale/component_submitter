from ast import literal_eval
import os.path

from flask import abort

from submitter import submitter_engine
from submitter import api as flask
from submitter import utils

_engine = submitter_engine.SubmitterEngine()


class Applications:
    """Class to access the Submitter engine object
    """

    def __init__(self, app_id=None):
        """
        Constructor

        Args:
            app_id (str, optional): App ID. If ommitted, the full app list
                will be returned. Defaults to None.
        """
        self.engine = _engine
        self.app_id = app_id

    def get(self):
        """Gets application information

        Returns:
            dict: Information on the requested application(s)
        """
        if not self.app_id:
            return self.engine.app_list
        try:
            return self.engine.app_list[self.app_id]
        except KeyError:
            abort(404, f"Application {self.app_id} does not exist")

    def create(self, adt=None, url=None, params=None, dryrun=False):
        """Deploys a new application in MiCADO

        Args:
            adt (flask.FileStorage OR dict, optional): ADT of the application.
                Ignored if URL provided, required if no URL. Defaults to None.
            url (str, optional): URL of the ADT for the application.
                Required if no file provided. Defaults to None.
            params (str repr OR dict, optional): Key-value pair mapping for
                TOSCA inputs. Defaults to None.
            dryrun (bool, optional): Dry run flag. Defaults to False.
        """
        if self._id_exists():
            abort(400, "The application ID already exists")
        elif self.engine.app_list:
            abort(400, "Multiple applications are not supported")

        path = self._get_path(adt, url)
        tpl, adaps = self._validate(path, params, dryrun)
        try:
            self.engine.launch(tpl, adaps, self.app_id, dryrun)
        except Exception as error:
            abort(500, f"Error while deploying: {error}")

        return {"message": f"Application {self.app_id} successfully deployed"}

    def update(self, adt=None, url=None, params=None):
        """Updates an existing application in MiCADO

        Args:
            adt (flask.FileStorage OR dict, optional): Modified ADT.
                Ignored if URL provided, required if no URL. Defaults to None.
            url (str, optional): URL of the modified ADT.
                Required if no file provided. Defaults to None.
            params (str repr OR dict, optional): Key-value pair mapping for
                TOSCA inputs. Defaults to None.
        """
        if not self._id_exists():
            abort(404, f"Application with ID {self.app_id} does not exist")
        elif not self.engine.app_list:
            abort(404, "There are no currently running applications")

        path = self._get_path(adt, url)
        tpl, adaps = self._validate(path, params, validate_only=True)
        try:
            self.engine.update(self.app_id, tpl, adaps)
        except Exception as error:
            abort(500, f"Error while updating: {error}")

        return {"message": f"Application {self.app_id} successfully updated"}

    def delete(self, force=False):
        """Deletes a running application

        Args:
            force (bool): Flag to force deletion
        """
        if not self._id_exists():
            abort(404, f"Application with ID {self.app_id} does not exist")
        elif not self.engine.app_list:
            abort(404, "There are no currently running applications")

        try:
            self.engine.undeploy(self.app_id, force)
        except Exception as error:
            abort(500, f"Error while deleting: {error}")

        TemplateHandler(self.app_id).delete_template()

        return {"message": f"Application {self.app_id} successfully deleted"}

    def _validate(self, path, params, dryrun=False, validate_only=False):
        """
        Call the engine validate method
        """
        params = _literal_params(params)
        try:
            template, adaptors = self.engine._validate(
                path, dryrun, validate_only, self.app_id, params
            )
        except Exception as error:
            abort(500, f"Error while validating: {error}")

        return template, adaptors

    def _get_path(self, adt, url):
        return url if url else TemplateHandler(self.app_id).save_template(adt)

    def _id_exists(self):
        """
        Returns True if the app_id exists on the server
        """
        return self.app_id in self.engine.app_list


class TemplateHandler:
    """
    Handles saving and deleting templates
    """

    def __init__(self, app_id):
        """Constructor, creates the template path

        Args:
            app_id (str): Application identifier
        """
        base_path = flask.app.root_path + "/" + "files/templates/"
        self.path = base_path + str(app_id)

    def save_template(self, adt):
        """
        Saves the template and returns the path
        """
        if not adt:
            abort(400, "No ADT data was included in the request")
        if not os.path.exists(os.path.dirname(self.path)):
            abort(500, f"Path {self.path} is not valid")

        if isinstance(adt, dict):
            utils.dump_order_yaml(adt, self.path)
        else:
            ext = adt.filename.split(".")[-1]
            self.path = self.path + "." + ext
            try:
                adt.save(self.path)
            except AttributeError:
                abort(400, "ADT data must be YAML file or dict")
        return self.path

    def delete_template(self):
        """
        Attempts to delete any template file for this application
        """
        try:
            os.remove(self.path)
        except Exception:
            pass


def _literal_params(params):
    """
    Converts string parsed-params into a dicitionary
    """
    if isinstance(params, dict):
        return params

    params = literal_eval(params) if params else {}
    if not isinstance(params, dict):
        abort(400, "Parsed params are not a valid map (dict)")
    return params
