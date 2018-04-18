from flask import request, url_for, Flask, jsonify
from submitter_engine import SubmitterEngine
from abstracts.exceptions import AdaptorCritical
app = Flask(__name__)

import logging
logger = logging.getLogger("submitter."+__name__)


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



# TODO: for each error that can happen create a funciton
#    - AdaptorError
#    - AdaptorWarning
#    - AdaptorCritical
@app.route('/engine/', methods=['POST'])
def engine():
    """ API functions to launch a application """
    #logger.debug("serving request {}".format(request.method))
    #path_to_file = str(request.data.get('input',''))
    path_to_file = request.form["input"]
    #logger.debug("the path_to_file is {}".format(path_to_file))
    #try:
    #    e=SubmitterEngine(path_to_file=path_to_file)
    #except AdaptorError as e:
    #    raise RequestError( e.message)
    #except AdaptorCritical as e:
    #    print("I'm here")
    #    raise RequestError(e.message)
    #except AdaptorWarning as e:
    #    raise RequestError(e.message)
    e = SubmitterEngine(path_to_file=path_to_file)
    if e is None:
        return "<h1> correctly launched</h1>"
    else:
        return "<h1>{}</1>".format(e)



if __name__ == "__main__":
    app.run(debug=True, port=5000)
