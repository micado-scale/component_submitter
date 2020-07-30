from submitter import submitter_engine

_engine = submitter_engine.SubmitterEngine()


class Applications:
    def __init__(self, api):
        self.engine = _engine
        self.api = api

    def get(self, app_id=None):
        if not app_id:
            return self.engine.app_list
        try:
            return self.engine.app_list[app_id]
        except KeyError:
            self.api.abort(404, f"Application {app_id} does not exist")
