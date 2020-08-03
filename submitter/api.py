from flask import Flask
from werkzeug.exceptions import HTTPException

from submitter.apis.apiv1 import apiv1
from submitter.apis.apiv2 import v2blueprint

app = Flask(__name__)
app.config["ERROR_404_HELP"] = False
app.register_blueprint(apiv1)
app.register_blueprint(v2blueprint, url_prefix="/v2.0/")


# The flask-restx errorhandler is broken so
# we use the flask errorhandler to pick up exceptions
@app.errorhandler(HTTPException)
def default_flask_error_handler(error):
    """Default error handler for HTTPException"""
    return {"message": str(error)}, getattr(error, "code", 500)
