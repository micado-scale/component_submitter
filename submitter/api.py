from flask import Flask
from werkzeug.exceptions import HTTPException

from submitter.apis.v1.api import v1blueprint
from submitter.apis.v2.controller import v2blueprint

app = Flask(__name__)

app.register_blueprint(v1blueprint)
app.register_blueprint(v2blueprint, url_prefix="/v2.0/")


@app.errorhandler(HTTPException)
def not_found_errors(error):
    return (
        {"message": str(error)},
        getattr(error, "code", 500),
    )
