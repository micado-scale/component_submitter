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
import threading
import time

def __init__():

    global logger, submitter, threads
    threads = dict()
    threads["list_threads"] = []
    threads["apps"] = []
    logger =  logging.getLogger("submitter."+__name__)
    submitter = SubmitterEngine()
    thread = threading.Thread(target=threads_management)
    thread.start()

def threads_management():
    while True:
        if threads["list_threads"]:
            logger.info("execute first thread of the list")
            name_thread_to_execute = threads["list_threads"][0]

            logger.info("{}".format(threads.get(name_thread_to_execute)))
            threads.get(name_thread_to_execute).start()
            threads.get(name_thread_to_execute).join()
            threads.pop(name_thread_to_execute)
            threads["list_threads"].pop(0)
            if "undeploy" in name_thread_to_execute:
                threads["apps"].pop(threads["apps"].index(name_thread_to_execute[9:]))

            time.sleep(2)
        else:
            time.sleep(2)
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
    response.status_code= 500
    return response

@app.errorhandler(RequestError)
def handle_request_error(error):
    logger.error("an exception occured {}".format(error))
    response = jsonify(error.to_dict())
    return response



@app.route('/v1.0/app/launch/', methods=['POST'])
def launch():
    """ API functions to launch a application

        :params intput: path to the file wanted
        :type input: string

        :params params: dictionary with the update of input.
        :type params: dictionary
    """
    response = dict(status_code="", message="", data=[])
    path_to_file = None
    try:
        path_to_file = request.form['input']
    except Exception:
        logger.info("no input provided")

    try:
        if not path_to_file:
            template = request.files['file']
    except Exception:
        logger.info("no file provided")

    try:
         id_app= request.form['id']
    except Exception:
         id_app = utils.id_generator()
    if id_app in threads["apps"]:
         response["message"] = "this id is already in use, please choose another one and try again."
         response["status_code"] = 400
         return jsonify(response)

    try:
         params= request.form['params']
    except Exception:
         parsed_params = None
    else:
        parsed_params = ast.literal_eval(params)

    if template:
        template.save("{}/files/templates/{}.yaml".format(app.root_path,id_app))
        path_to_file = "files/templates/{}.yaml".format(id_app)

    thread = threading.Thread(target=submitter.launch,args=(path_to_file, id_app, parsed_params), daemon=True)
    threads["list_threads"].append("launch_{}".format(id_app))
    threads["launch_{}".format(id_app)] = thread
    threads["apps"].append(id_app)
    response["message"] = "Thread to deploy application launched. To check process curl http://YOUR_HOST/v1.0/{}/status".format(id_app)
    response["status_code"]= 200
    return jsonify(response)




@app.route('/v1.0/app/undeploy/<id_app>', methods=['DELETE'])
def undeploy(id_app):
    """ API function to undeploy the application with a specific ID
    """
    response = dict(status_code="", message="", data=[])

    try:
        if "undeploy_{}".format(id_app) in threads["list_threads"]:
            response["message"] = "this application has already undeploy acction  pending."
            repsonse["status_code"] = 400
            return jsonify(response)

        thread = threading.Thread(target=submitter.undeploy, args=(id_app,), daemon=True)
        threads["list_threads"].append("undeploy_{}".format(id_app))
        threads["undeploy_{}".format(id_app)] = thread
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


@app.route('/v1.0/app/update/<id_app>', methods=['PUT'])
def update(id_app):
    """ API function to update the application with a specific ID"""

    response = dict(status_code="", message="", data=[])
    path_to_file = None
    if "update_{}".format(id_app) in threads["list_threads"]:
        response["message"] = "this application has already an update pending, please wait for it to be completed before sending a new one."
        response["status_code"] = 400
        return jsonify(response)
    try:
        path_to_file = request.form['input']
    except Exception:
        logger.info("no input provided")

    try:
        if not path_to_file:
            template = request.files['file']
    except Exception:
        logger.info("no file provided")
    try:
         params= request.form['params']
    except Exception:
         parsed_params = None
    else:
        parsed_params = ast.literal_eval(params)

    if template:
        template.save("{}/files/templates/{}.yaml".format(app.root_path,id_app))
        path_to_file = "files/templates/{}.yaml".format(id_app)
    try:
        thread = threading.Thread(target=submitter.update, args=(id_app, path_to_file, parsed_params), daemon=True)
        threads["list_threads"].append("update_{}".format(id_app))
        threads["launch_{}".format(id_app)] = thread
        response["message"] = "Thread to update the application {} is launch. To check process curl http://YOUR_HOST/v1.0/{}/status ".format(id_app)
        response["status_code"]= 200
        return jsonify(response)
    except Exception:
        response["message"] = "{} update failed".format(id_app)
        response["status_code"]= 500
        return jsonify(response)


@app.route('/v1.0/app/<id_app>', methods=['GET'])
def info_app(id_app):
    """ API function to get the information on a given id """
    response = dict(status_code="", message="", data=[])
    try:
        this_app = submitter.app_list[id_app]
        this_app_status = submitter.get_status(id_app)

        if "launch_{}".format(id_app) in threads["list_threads"]:
            if "launch_{}".format(id_app) not in threads["list_threads"][0]:
                this_app_status = "pending, other application in the queue."



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
                                components=this_app["components"],
                                status=this_app_status)

        return jsonify(response)


@app.route('/v1.0/app/query/<id_app>', methods=['GET'])
def query(id_app):
    """ API call to query running services """
    response = dict(status_code=200, message="List running nodes", data=[])
    query = request.form['query']
    for result in submitter.query(query, id_app):
        response['data'].append(result)
    return jsonify(response)


@app.route('/v1.0/info_threads')
def list_thread():
    """ API call to query the info on the thread being executed"""
    response = dict(status_code=200, message="Info on Thread", data=[])
    try:
        response['data']={"thread being executed": threads["list_threads"][0], "list of threads waiting" : threads["list_threads"][1:]}
    except:
        response["status_code"] = 500
        response["message"] = "failed retriving info of threads"
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
