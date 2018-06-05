from flask import request, url_for, Flask, jsonify, render_template, flash, redirect
from submitter_engine import SubmitterEngine
from abstracts.exceptions import AdaptorCritical
from werkzeug import secure_filename
import os
app = Flask(__name__)
UPLOAD_FOLDER="/Users/greg/Desktop/work/COLA/submitter/greg_fork/component_submitter/files/tests/"
app.config['UPLOAD_FOLDER']=UPLOAD_FOLDER
import logging
import ast
import utils
import yaml


def __init__():

    global logger, submitter

    logger =  logging.getLogger("submitter."+__name__)
    submitter = SubmitterEngine()

__init__()
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



@app.route('/v1.0/app/launch/url/', methods=['POST'])
def engine_url():
    """ API functions to launch a application

        :params intput: path to the file wanted
        :type input: string

        :params params: dictionary with the update of input.
        :type params: dictionary
    """
    logger.debug("serving request {}".format(request.method))


    path_to_file = request.form["input"]
    logger.debug("path_to_file: {}".format(path_to_file))
    try:
        id_app =  request.form["id"]
    except Exception as e:
        logger.info("no id params has been sent, setting it to None")
        id_app = None

    try:
        params = request.form['params']
        logger.info("params is {}".format(params))

    except Exception as e:
        logger.info("exception is: {}".format(e))
        id_app = submitter.launch(path_to_file=path_to_file, id_app=id_app)

    else:
        parsed_params = ast.literal_eval(params)
        id_app = submitter.launch(path_to_file=path_to_file, parsed_params=parsed_params, id_app=id_app)
    response = jsonify(dict(message="app:{}".format(id_app)))
    response.status_code = 200
    return response

@app.route('/v1.0/app/launch/file/', methods=['POST'])
def engine_file():
    """ API functions to launch a application

        stream.read() file

    """
    # try:
    #     f = request.files
    #     logger.debug(f)
    #
    # except Exception as e:
    #     logger.debug(e)
    #     return e.message
    # #f.save(secure_filename(f.filename))
    # return 'file uploaded successfully'
    #logger.debug("template: {}".format(template_yaml))
    f = request.files['file']
    try:
         id_app= request.form['id']
    except Exception:
         id_app = utils.id_generator()

    try:
         params= request.form['params']
    except Exception:
         parsed_params = None
    else:
        parsed_params = ast.literal_eval(params)

    f.save("{}/files/templates/{}.yaml".format(app.root_path,id_app))
    path_to_file = "files/templates/{}.yaml".format(id_app)

    id_app = submitter.launch(path_to_file = path_to_file, parsed_params=parsed_params, id_app=id_app)
    response = jsonify(dict(message="app:{}".format(id_app)))
    response.status_code = 200
    return response
    #return "True"
# @app.route('/v1.0/app/launch/file/', methods=['POST'])
# def engine_file_no_id():
#     f = request.files['file']
#
#
#     logger.debug(f)
#     return "true"
# #    parsed_params = request.form['params']
#     #app_id = request.form['id']
#     #template_yaml = request.stream.read()
#     #logger.debug(template_yaml)
#     #app_id = utils.id_generator()
#     #utils.dump_order_yaml(yaml.safe_load(template_yaml), "files/templates/{}.yaml".format(app_id))
#     #logger.debug("template is: {}".format(app_id))
#     #return "True"
#


@app.route('/v1.0/app/undeploy/<id_app>', methods=['DELETE'])
def undeploy(id_app):
    """ API function to undeploy the application with a specific ID
    """
    response = submitter.undeploy(id_app)
    if response is None:
        return jsonify(dict(message="undeployed {} correctly".format(id_app), status_code=200))
    else:
        return jsonify(dict(message="something undexpected happened", status_code=500))

@app.route('/v1.0/app/update/<id_app>', methods=['PUT'])
def update(id_app):
    """ API function to deploy the application with a specific ID """
    logger.info("id is: {}".format(id_app))
    path_to_file = request.form['input']
    logger.info("path_to_file is: {}".format(path_to_file))
    try:
        params = request.form['params']
        logger.info("params is: {}".format(params))
        parsed_params = ast.literal_eval(params)
    except Exception as e:
        logger.info("exception is: {}".format(e))
        response = submitter.update(id_app, path_to_file)
        if response is None:
            return jsonify(dict(message="correctly updated", status_code=200))
        else:
            return jsonify(dict(message="update failed", status_cod=500))
    else:
        response = submitter.update(id_app, path_to_file, parsed_params)
        if response is None:
            return jsonify(dict(message="correctly updated", status_code=200))
        else:
            return jsonify(dict(message="update failed", status_cod=500))



@app.route('/v1.0/app/<id_app>', methods=['GET'])
def info_app(id_app):
    response = jsonify(dict(message="{}".format(submitter.app_list[id_app])))
    response.status_code = 500


    return response

@app.route('/v1.0/list_app', methods=['GET'])
def list_app():
    response = []
    for key, value in submitter.app_list.items():
        response.append("id: {}, outputs: {}\n".format(key,value))
    return "<h1>here is the id list of applications \n {}\n</h1>\n".format(response)

if __name__ == "__main__":
    __init__()
    app.run(debug=True, port=5000, threaded=True)
