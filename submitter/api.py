from flask import Flask

from submitter.apis.apiv1 import apiv1

app = Flask(__name__)
app.register_blueprint(apiv1)