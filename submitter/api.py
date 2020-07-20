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
import queue
import time
import urllib.request
import json

JSON_FILE = "system/ids.json"

def __init__():

    global logger, submitter, queue_exception, queue_threading
            
    logger =  logging.getLogger("submitter."+__name__)     
    submitter = SubmitterEngine()
    queue_exception = queue.Queue()
    queue_threading = queue.Queue()
    thread = threading.Thread(target=threads_management)
    thread.start()



class ExecSubmitterThread(threading.Thread):
    def __init__(self, q, *args, **kwargs):
        super(ExecSubmitterThread, self).__init__(*args, **kwargs)

        self.q = q

    def run(self):
        try:
            self._target(*self._args, **self._kwargs)
        except Exception as e:
            exception = {"name":self.getName(), "exception": e}
            self.q.put(exception)



def threads_management():
    global current_thread, last_error
    last_error = ''
    current_thread = ''
    while True:
        time.sleep(3)
        if not queue_threading.empty():
           thread = queue_threading.get()
           current_thread = thread.getName()
           thread.start()
           thread.join()
        try:
           if not queue_exception.empty():
               exception = queue_exception.get()
               logger.error("exception caught on thread {}".format(exception["name"]))
               raise exception["exception"]

        except Exception as e:
            last_error = e
            logger.info("{}".format(e))


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
        dryrun = request.form['dryrun']
        if dryrun == 'True':
            dryrun = True
        else:
            dryrun = False
    except Exception:
        dryrun = False

    if submitter.app_list.keys():
        response["message"] = "An application is already running, MiCADO doesn't currently support multiple applications"
        response["status_code"] = 400
        return jsonify(response)
    
    try:
        path_to_file = request.form['input']
        logger.debug("User provided a URL for the application template")
    except Exception:
        pass

    try:
        if not path_to_file:
            template = request.files['file']
            logger.debug("User provided a local file for the application template")       
    except Exception:
        logger.error("Neither a correct URL nor a local file has been provided for the application template")
        response["message"] = "Application template is required; please provide a correct URL or file for the application template"
        response["status_code"] = 400
        return jsonify(response)
        

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

    if template:
        template.save("{}/files/templates/{}.yaml".format(app.root_path,id_app))
        path_to_file = "files/templates/{}.yaml".format(id_app)

    if id_app in submitter.app_list.keys():
        response["message"] = "id already register on this service"
        response["status_code"] = 400
        return jsonify(response)

    try:
        template, dict_object_adaptors = submitter._validate(path_to_file, dryrun, False, id_app, parsed_params)
    except Exception as error:
        logger.error(error)
        response["message"]= "The application is not valid: {}".format(error)
        response["status_code"]= 422
        return jsonify(response)
    thread = ExecSubmitterThread(q=queue_exception, target=submitter.launch, args=(template, dict_object_adaptors, id_app, dryrun), daemon=True)
    thread.setName("launch_{}".format(id_app))
    queue_threading.put(thread)

    response["message"] = "Thread to deploy application launched. To check the progress: curl --insecure -u <MICADO_ADMIN_USER>:<MICADO_ADMIN_PASS> https://<MICADO_MASTER_IP>:<MICADO_MASTER_PORT>/toscasubmitter/v1.0/app/{}/status".format(id_app)
    response["status_code"]= 200
    global last_error
    last_error = ''
    return jsonify(response)

@app.route('/v1.0/app/validate/', methods=['POST'])
def validate():
    """ API functions to validate a TOSCA template provided by the user

        :params intput: path to the file wanted
        :type input: string

        :params params: dictionary with the update of input.
        :type params: dictionary
    """
    response = dict(status_code="", message="", data=[])
    path_to_file = None
    validate= True

    try:
        path_to_file = request.form['input']
        logger.debug("User provided a URL for the application template")
    except Exception:
        pass

    try:
        if not path_to_file:
            template = request.files['file']
            logger.debug("User provided a local file for the application template")       
    except Exception:
        logger.error("Neither a correct URL nor a local file has been provided for the application template")
        response["message"] = "Application template is required; please provide a correct URL or file for the application template"
        response["status_code"] = 400
        return jsonify(response)

    if template:
        template.save("{}/files/templates/template.yaml".format(app.root_path))
        path_to_file = "files/templates/template.yaml"

    submitter._validate(path_to_file, validate=True)

    response["message"] = "The provided application template is valid"
    response["status_code"]= 200
    return jsonify(response)


@app.route('/v1.0/app/undeploy/<id_app>', methods=['DELETE'])
def undeploy(id_app):
    """ API function to undeploy the application with a specific ID
    """
    response = dict(status_code="", message="", data=[])
    try:
        if 'force' in request.form:
            thread = ExecSubmitterThread(q=queue_exception, target=submitter.undeploy, args=(id_app, True), daemon=True)
            thread.setName("undeploy_{}".format(id_app))
            queue_threading.put(thread)
            logger.info("force flag found")
            response["status_code"]=200
            response["message"]= "correctly send force undeploy command to MiCADO master."
            return jsonify(response)
    except Exception:
        logger.debug("no force flag found")
    
    if not submitter.app_list.keys():
        response["message"] = "There is no running applications to undelploy"
        response["status_code"] = 400
        return jsonify(response)
    elif id_app not in submitter.app_list.keys():
        logger.warning("Trying to undeploy an application with a non-existing id")
        response["message"] = "There is no running application with ID={}, please use a correct application ID".format(id_app)
        response["status_code"] = 400
        return jsonify(response)

    for item in queue_threading.queue:
        if "undeploy_{}".format(id_app) in item.getName():
            logger.debug("The application with id={} has already undeploy action pending")
            response["message"] = "this application has already undeploy action pending."
            response['status_code'] = 400
            return jsonify(response)
    thread = ExecSubmitterThread(q=queue_exception, target=submitter.undeploy, args=(id_app,), daemon=True)
    thread.setName("undeploy_{}".format(id_app))
    queue_threading.put(thread)

    logger.debug("successfully send undeploy request for {} to MiCADO master".format(id_app))
    response["message"] = "successfully send undeployed for {} to MiCADO master".format(id_app)
    response["status_code"] = 200
    global last_error
    last_error = ''
    return jsonify(response)


@app.route('/v1.0/app/update/<id_app>', methods=['PUT'])
def update(id_app):
    """ API function to update the application with a specific ID"""

    response = dict(status_code="", message="", data=[])
    path_to_file = None

    if not submitter.app_list.keys():
        response["message"] = "There is no running applications to update"
        response["status_code"] = 400
        return jsonify(response)
    elif id_app not in submitter.app_list.keys():
        response["message"] = "There is no running application with ID={}, please use a correct application ID to update".format(id_app)
        response["status_code"] = 400
        return jsonify(response)

    for item in queue_threading.queue:
        if "update_{}".format(id_app) in item.getName():
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
        dryrun = submitter.app_list[id_app]["dry_run"]
        template, dict_object_adaptors = submitter._validate(path_to_file, dryrun, True, id_app, parsed_params)

    except Exception as error:
        logger.error(error)
        response["message"]= "The application is not valid: {}".format(error)
        response["status_code"]= 422
        return jsonify(response)
    try:
        thread = ExecSubmitterThread(q=queue_exception, target=submitter.update, args=(id_app, template, dict_object_adaptors), daemon=True)
        thread.setName("update_{}".format(id_app))
        queue_threading.put(thread)
        response["message"] = "Thread to update the application is launch. To check process curl http://YOUR_HOST/v1.0/app/{}/status ".format(id_app)
        response["status_code"]= 200
        global last_error
        last_error = ''
        return jsonify(response)
    except Exception:
        response["message"] = "{} update failed".format(id_app)
        response["status_code"]= 500
        return jsonify(response)


@app.route('/v1.0/app/<id_app>/status', methods=['GET'])
def info_app(id_app):
    """ API function to get the information on a given id """
    response = dict(status_code="", message="", data=[])
    try:
        this_app = submitter.app_list[id_app]
        this_app_status = submitter.get_status(id_app) or 'Could not get status'
        q_t = queue_threading.queue

        if not "launch_{}".format(id_app) in current_thread:
            for item in q_t:
                if "launch_{}".format(id_app) in item.getName():
                    this_app_status = "pending, other application in the queue."

    except KeyError:
        response["status_code"]=404
        response["message"]="App with ID {} does not exist".format(id_app)
        if last_error:
            response["data"].append('Error on last threaded action: {}'.format(last_error))

        return jsonify(response)
    else:
        response["status_code"]=200
        response["message"]="Detail application {}".format(id_app)
        response["data"] = dict(type="application",
                                id=id_app,
                                outputs=this_app.get("output"),
                                components=this_app.get("components"),
                                status=this_app_status)

        return jsonify(response)


@app.route('/v1.0/app/query/<id_app>', methods=['GET'])
def query(id_app):
    """ API call to query running services """
    query = request.form['query']
    response = dict(status_code=200, message="Query: {}".format(query), data=[])
    for result in submitter.query(query, id_app):
        response['data'].append(result)
    return jsonify(response)


@app.route('/v1.0/info_threads')
def list_thread():
    """ API call to query the info on the thread being executed"""
    response = dict(status_code=200, message="Info on Thread", data=[])
    try:
        q_t=list()
        for item in queue_threading.queue:
            q_t.append(item.getName())
        response['data']={"thread being executed": current_thread , "list of threads waiting" : q_t}
    except Exception as e:
        logger.info(e)
        response["status_code"] = 500
        response["message"] = "failed retriving info of threads"
    return jsonify(response)

@app.route('/v1.0/list_app', methods=['GET'])
def list_app():
    """ API function to list all the running aplications"""
    response = dict(status_code=200, message="List running applications", data=[])
    if not submitter.app_list.keys():
        response["message"] = "There are no running applications"
        response["status_code"] = 200
        return jsonify(response)

    for key, value in submitter.app_list.items():
        #if dryrun:
        #    response["message"]="Application {} deployed in DRY-RUN mode".format(key)
        response["data"].append(dict(type="application",
                                    id=key,
                                    outputs=value.get("output"),
                                    components=value.get("components"),
                                    dryrun=value.get("dry_run")))
    return jsonify(response)

if __name__ == "__main__":
    __init__()
    app.run(debug=True, port=5000, threaded=True)
