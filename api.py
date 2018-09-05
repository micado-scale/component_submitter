from flask import request, url_for, Flask, jsonify, render_template, flash, redirect
from submitter_engine import SubmitterEngine
from toscaparser.common.exception import *
import os
app = Flask(__name__)
app.url_map.strict_slashes = False
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
    response["status_code"]= 500
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
    response = dict(status_code="", message="", data=[])

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

    response["status_code"] = 200
    response["message"] = "successfully launched app {}".format(id_app)
    return jsonify(response)

@app.route('/v1.0/app/launch/file/', methods=['POST'])
def engine_file():
    """ API functions to launch an application
    """
    response = dict(status_code="", message="", data=[])
    template = request.files['file']
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

    template.save("{}/files/templates/{}.yaml".format(app.root_path,id_app))
    path_to_file = "files/templates/{}.yaml".format(id_app)


    id_app = submitter.launch(path_to_file = path_to_file, parsed_params=parsed_params, id_app=id_app)

    response["message"] = "successfully launched app {}".format(id_app)
    response["status_code"]= 200
    return jsonify(response)



@app.route('/v1.0/app/undeploy/<id_app>', methods=['DELETE'])
def undeploy(id_app):
    """ API function to undeploy the application with a specific ID
    """
    response = dict(status_code="", message="", data=[])

    try:
        submitter.undeploy(id_app)
        response["message"] = "successfully undeployed {}".format(id_app)
        response["status_code"] = 200
        return jsonify(response)
    except Exception:
        response["message"] = "application {} doesn't exist".format(id_app)
        response["status_code"] = 404
        return jsonify(response)
    else:
        response["message"] = "something unexpected happened, contact your MiCADO Admin for more details"
        response["status_code"]= 500
        return jsonify(response)

@app.route('/v1.0/app/update/url/<id_app>', methods=['PUT'])
def update_url(id_app):
    """ API function to update the application with a specific ID from a url"""
    logger.info("id is: {}".format(id_app))
    path_to_file = request.form['input']
    logger.info("path_to_file is: {}".format(path_to_file))
    response = dict(status_code="", message="", data=[])
    try:
        params = request.form['params']
        logger.info("params is: {}".format(params))
        parsed_params = ast.literal_eval(params)
    except Exception as e:
        logger.info("exception is: {}".format(e))
        if submitter.update(id_app, path_to_file) is None:
            response["message"] = "{} correctly updated".format(id_app)
            response["status_code"]= 200
            return jsonify(response)
        else:
            response["message"] = "{} update failed".format(id_app)
            response["status_code"]= 500
            return jsonify(response)
    else:

        if submitter.update(id_app, path_to_file, parsed_params) is None:
            response["message"] = "{} correctly updated".format(id_app)
            response["status_code"]= 200
            return jsonify(response)
        else:
            response["message"] = "{} update failed".format(id_app)
            response["status_code"]= 500
            return jsonify(response)

@app.route('/v1.0/app/update/file/<id_app>', methods=['PUT'])
def update_file(id_app):
    """ API function to update the application with a specific ID from a file"""
    template = request.files['file']
    response = dict(status_code="", message="", data=[])
    try:
         params= request.form['params']
    except Exception:
         parsed_params = None
    else:
        parsed_params = ast.literal_eval(params)

    template.save("{}/files/templates/{}.yaml".format(app.root_path,id_app))
    path_to_file = "files/templates/{}.yaml".format(id_app)

    if submitter.update(id_app, path_to_file=path_to_file, parsed_params=parsed_params) is None:
        response["message"] = "{} correctly updated".format(id_app)
        response["status_code"]= 200
        return jsonify(response)
    else:
        response["message"] = "{} update failed".format(id_app)
        response["status_code"]= 500
        return jsonify(response)

@app.route('/v1.0/app/<id_app>', methods=['GET'])
def info_app(id_app):
    """ API function to get the information on a given id """
    response = dict(status_code="", message="", data=[])
    try:
        this_app = submitter.app_list[id_app]
    except KeyError:
        response["status_code"]=404
        response["message"]="App with ID {} does not exist".format(id_app)

        return jsonify(response)
    else:
        response["status_code"]=200

        response["message"]="Detail application {}".format(id_app)
        response["data"] = dict(type="application",
                                id=id_app,
                                outputs=this_app["output"],
                                components=this_app["components"])
        return jsonify(response)

@app.route('/v1.0/app/<id_app>/services', methods=['GET'])
def services_query(id_app):
    """ API call to query running services """
    response = dict(status_code=200, message="List running services", data=[])
    for result in submitter.query('services', id_app):
        response['data'].append(result)
    return jsonify(response)

@app.route('/v1.0/app/<id_app>/nodes', methods=['GET'])
def nodes_query(id_app):
    """ API call to query running services """
    response = dict(status_code=200, message="List running nodes", data=[])
    for result in submitter.query('nodes', id_app):
        response['data'].append(result)
    return jsonify(response)

@app.route('/v1.0/list_app', methods=['GET'])
def list_app():
    """ API function to list all the running aplications"""
    response = dict(status_code=200, message="List running applications", data=[])
    for key, value in submitter.app_list.items():
        response["data"].append(dict(type="application",
                                     id=key,
                                     outputs=value["output"],
                                     components=value["components"]))
    return jsonify(response)

if __name__ == "__main__":
    __init__()
    app.run(debug=True, port=5000, threaded=True)
