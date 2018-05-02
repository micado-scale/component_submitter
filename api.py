from flask import request, url_for, Flask, jsonify, render_template
from submitter_engine import SubmitterEngine
from abstracts.exceptions import AdaptorCritical
import os
app = Flask(__name__)
import utils
import logging



def __init__():

    global logger, submitter

    logger =  logging.getLogger("submitter."+__name__)
    submitter = SubmitterEngine()


class RequestError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv



def keyboardInterrupt():
    logger.info('Ctrl+C - Exiting.')
    for i in manager.process_table.iterkeys():
        logger.info("Infrastructure left running: {}".format(i))

@app.errorhandler(Exception)
def unhandle_request_error(error):
    import traceback as tb
    logger.error("An unhandle exception occured:{}".format(error))
    response = jsonify(dict(message=str(error)))
    response.status_code = 500
    return response

@app.errorhandler(RequestError)
def handle_request_error(error):
    logger.error("an exception occured {}".format(error))
    response = jsonify(error.to_dict())
    return response



@app.route('/engine/', methods=['POST'])
def engine():
    """ API functions to launch a application """
    logger.debug("serving request {}".format(request.method))
    path_to_file = request.form["input"]
    response = submitter.launch(path_to_file=path_to_file)
    return "<h1>\nthe id of the launch application is: {} \n</h1>\n".format(response)

@app.route('/undeploy/', methods=['POST'])
def undeploy():
    """ API function to undeploy the application with a specific id """
    id_app = request.form["id_app"]
    response = submitter.undeploy(id_app)
    if response is None:
        return "<h1>correctly undeployed</h1>\n"
    else:
        return "<h1>{}</h1>\n".format(response)

@app.route('/list_app', methods=['GET'])
def list_app():
    response = []
    for key, value in submitter.id_dict.items():
        response.append(key)
    return "<h1>here is the id list of applications \n {}\n</h1>\n".format(response)

if __name__ == "__main__":
    __init__()
    app.run(debug=True, port=5000, threaded=True)
