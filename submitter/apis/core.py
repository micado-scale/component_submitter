from ast import literal_eval

from submitter import submitter_engine

_engine = submitter_engine.SubmitterEngine()


class Applications:
    """Class to access the Submitter engine object
    """
    def __init__(self, api):
        """Constructor

        Args:
            api (flask_restx api Object): The api calling the submitter
        """
        self.engine = _engine
        self.api = api

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
            self.api.abort(404, f"Application {app_id} does not exist")


def literal_params(params):
    """Converts string parsed-params into a dicitionary

    Args:
        params (string): TOSCA-parser parsed params
    """
    return literal_eval(params)
