from flask import Flask

from submitter.apis.apiv1 import apiv1
from submitter.apis.apiv2 import v2blueprint

app = Flask(__name__)
app.config["ERROR_404_HELP"] = False
app.register_blueprint(apiv1)
app.register_blueprint(v2blueprint, url_prefix="/v2.0/")
