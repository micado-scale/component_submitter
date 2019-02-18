from micado_parser import MiCADOParser
from plugins_gestion import PluginsGestion
import sys
from micado_validator import MultiError
from abstracts.exceptions import AdaptorCritical, AdaptorError
import utils
import json
import ruamel.yaml as yaml
import os
import time
from random import randint
from submitter_config import SubmitterConfig
import logging
""" set up of Logging """
config = SubmitterConfig()
LEVEL = config.main_config['log_level']
FILENAME = config.main_config['path_log']
logging.basicConfig(filename=FILENAME, level=LEVEL, format="%(asctime)s - %(lineno)d - %(name)s - %(levelname)s - %(message)s")
logger=logging.getLogger("submitter."+__name__)

"""define the Handler which write message to sys.stderr"""
console = logging.StreamHandler()
console.setLevel(LEVEL)
""" set format which is simpler for console use"""
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')

console.setFormatter(formatter)

""" add the handler to the root logger"""
logging.getLogger('').addHandler(console)

JSON_FILE = "system/ids.json"


class SubmitterEngine(object):
    """ SubmitterEngine class that is the main one that is used to treat with the application. """
    def __init__(self):
        """
        instantiate the SubmitterEngine class. Retrieving the JSON_DATA file to see if there's any
        other application that were already launched previously, if not creation of it.
        """
        super(SubmitterEngine, self).__init__()
        logger.debug("init of submitter engine class")

        try:
            with open(JSON_FILE, 'r') as json_data:
                logger.debug("instantiation of dictionary app_list with {}".format(JSON_FILE))
                self.app_list = json.load(json_data)
        except FileNotFoundError:
            logger.debug("file {} doesn't exist so isntantiation of empty directory of app_list".format(JSON_FILE))
            self.app_list = dict()
        logger.debug("load configurations")
        self.object_config = SubmitterConfig()
        self.adaptors_class_name = []
        self._get_adaptors_class()

        self.translated_adaptors = {}
        self.executed_adaptors = {}

    def launch(self, path_to_file, id_app, parsed_params=None):
        """
        Launch method, that will call the in-method egine to execute the application
        Creating empty list for the whole class adaptor and executed adaptor
        :params: path_to_file, parsed_params
        :types: string, dictionary
        .. note::
            For the time being we only have one "workflow engine" but we could extend this
            launch method to accept another parameter to be able to choose which engine to
            launch
        """

        logger.info("******  Launching the application ****** \n****** located there {} and with params {}******".format(path_to_file, parsed_params))
        if self.app_list and not self.object_config.main_config['dry_run']:
            raise Exception("An application is already running, MiCADO doesn't currently support multi applications")
            
        template = self._micado_parser_upload(path_to_file, parsed_params)
        self.object_config.mapping(template)

        dict_object_adaptors = self._instantiate_adaptors(id_app, template)
        logger.debug("list of objects adaptor: {}".format(dict_object_adaptors))
        #self._save_file(id_app, path_to_file)
        self.app_list.update({id_app: {"components":list(dict_object_adaptors.keys()), "adaptors_object": dict_object_adaptors}})
        self._update_json()
        logger.debug("dictionnaty of id is: {}".format(self.app_list))

        self._engine(dict_object_adaptors, template, id_app)

        logger.info("launched process done")
        logger.info("*********************")
        return id_app

    def undeploy(self, id_app, force=False):
        """
        Undeploy method will remove the application from the infrastructure.
        :params: id
        :type: string
        """
        logger.info("****** proceding to the undeployment of the application *****")

        try:
            if id_app not in self.app_list.keys() and not force:
                raise Exception("application doesn't exist")
        except AttributeError:
            logger.error("no application has been detected on the infrastructure trying to see if force flag present")
            if not force:
                raise Exception("no application detected")
            else:
                logger.info("force flag detected, preceeding to undeploy")


        dict_object_adaptors = self._instantiate_adaptors(id_app)
        logger.debug("{}".format(dict_object_adaptors))


        self._undeploy(dict_object_adaptors)

        self._cleanup(id_app, dict_object_adaptors)
        if self.app_list:
            self.app_list.pop(id_app)
            self._update_json()
        logger.info("undeploy process done")
        logger.info("*********************")


    def update(self, id_app, path_to_file, parsed_params = None):
        """
        Update method that will be updating the application we want to update.

        :params id: id of the application we want to update
        :params type: string

        :params path_to_file: path to the template file
        :params type: string

        :params parse_params: dictionary containing the value we want to use as the value of the input section
        :params type: dictionary

        """

        logger.info("****** proceding to the update of the application {}******".format(id_app))

        template = self._micado_parser_upload(path_to_file, parsed_params)
        self.object_config.mapping(template)
        dict_object_adaptors = self._instantiate_adaptors(id_app, template)
        logger.debug("list of adaptor created: {}".format(dict_object_adaptors))
        self.app_list.update({id_app: {"components":list(dict_object_adaptors.keys()), "adaptors_object": dict_object_adaptors}})
        self._update_json()
        self._update(dict_object_adaptors, id_app)
        logger.info("update process done")
        logger.info("*******************")


    def _engine(self,adaptors, template, app_id):
        """ Engine itself. Creates first a id, then parse the input file. Retreive the list of id created by the translate methods of the adaptors.
        Excute those id in their respective adaptor. Update the app_list and the json file.
        """
        try:
            self._translate(adaptors)
            self._execute(app_id, adaptors)
            logger.debug(self.executed_adaptors)

        except MultiError:
            raise
        except AdaptorCritical as e:
            logger.info("******* Critical error during deployment, starting to roll back *********")
            if self.executed_adaptors:
                logger.info("Starting undeploy on executed components")
                self._undeploy(self.executed_adaptors)
            if self.translated_adaptors:
                logger.info("Starting clean-up on translated files")
                self._cleanup(app_id, self.translated_adaptors)
            if self.app_list:
                logger.info("Removing application ID from deployment")
                self.app_list.pop(app_id)
                self._update_json()

            logger.info("The deployment wasn't successful...")
            logger.info("*******************")
            raise

    def _micado_parser_upload(self, path, parsed_params):
        """ Parse the file and retrieve the object """
        logger.debug("instantiation of submitter and retrieve template")
        parser = MiCADOParser()
        template= parser.set_template(path=path, parsed_params=parsed_params)
        logger.info("Valid & Compatible TOSCA template")
        return template


    def _get_adaptors_class(self):
        """ Retrieve the list of the differrent class adaptors """
        logger.debug("retreive the adaptors class")
        adaptor_list = self.object_config.get_list_adaptors()
        PG=PluginsGestion()
        for k in adaptor_list:
            adaptor = PG.get_plugin(k)
            logger.debug("adaptor found {}".format(adaptor))
            self.adaptors_class_name.append(adaptor)
        logger.debug("list of adaptors instantiated: {}".format(self.adaptors_class_name))


    def _instantiate_adaptors(self, app_id, template = None):
        """ Instantiate the list of adaptors from the adaptors class list

            :params app_id: id of the application
            :params app_ids: list of ids to specify the adaptors (can be None)
            :params template: template of the application

            if provide list of adaptors object and app_id

            :returns: list of adaptors

        """
        adaptors = dict()
        if template is not None:
            for adaptor in self.adaptors_class_name:
                logger.debug("instantiate {}, template".format(adaptor))
                adaptor_id="{}_{}".format(app_id, adaptor.__name__)
                obj = adaptor(adaptor_id, self.object_config.adaptor_config[adaptor.__name__], template = template)
                adaptors[adaptor.__name__] = obj
                #adaptors.append(obj)
            return adaptors

        elif template is None:
            for adaptor in self.adaptors_class_name:
                logger.debug("instantiate {}, no template".format(adaptor))
                adaptor_id="{}_{}".format(app_id, adaptor.__name__)
                obj = adaptor(adaptor_id,self.object_config.adaptor_config[adaptor.__name__])
                #adaptors.append(obj)
                adaptors[adaptor.__name__] = obj

                logger.debug("done instntiation of {}".format(adaptor))

            return adaptors


    def _translate(self, adaptors):
        """ Launch the translate engine """
        logger.debug("launch of translate method")
        logger.info("translate method called in all the adaptors")
        self.translated_adaptors = {}

        for step in self.object_config.step_config['translate']:
            logger.info("translating method call from {}".format(step))
            while True:
                try:
                    self.translated_adaptors[step] = adaptors[step]
                    adaptors[step].translate()
                except AdaptorError:
                    continue
                break

    def _execute(self, app_id, adaptors):
        """ method called by the engine to launch the adaptors execute methods """
        logger.info("launch of the execute methods in each adaptors in a serial way")
        self.executed_adaptors = {}
        self.app_list.setdefault(app_id, {}).setdefault("output", {})
        for step in self.object_config.step_config['execute']:
            self.executed_adaptors[step] = adaptors[step]
            adaptors[step].execute()
            output = getattr(adaptors[step], "output", None)
            if output:
                self.app_list[app_id]["output"].update({step:output})

        self._update_json()

    def _undeploy(self, adaptors):
        """ method called by the engine to launch the adaptor undeploy method of a specific component identified by its ID"""
        logger.info("undeploying component")
        for step in self.object_config.step_config['undeploy']:
            try:
                adaptors[step].undeploy()
            except KeyError as e:
                logger.debug("{} not in initialised/executed adaptors, skipping...".format(e))
            except Exception as e:
                logger.error("error: {}; proceeding to undepployment of the other adaptors".format(e))

    def _update(self, adaptors, app_id):
        """ method that will translate first the new component and then see if there's a difference, and then execute"""
        logger.info("update of each components related to the application wanted")
        self.app_list.setdefault(app_id, {}).setdefault("output", {})
        for step in self.object_config.step_config['update']:
            adaptors[step].update()
            output = getattr(adaptors[step], "output", None)
            if output:
                self.app_list[app_id]["output"].update({step:output})

    def query(self, query, app_id):
        """ query """
        for adaptor in self._instantiate_adaptors(app_id).values():
            try:
                result = adaptor.query(query)
            except AttributeError:
                continue
            else:
                return result
        else:
            raise AdaptorCritical("No query method available")

    def get_status(self, app_id):
        """ method to retrieve the status of the differents adaptor"""
        try:
            result = dict()
            for key, value in self.app_list[app_id].get("adaptors_object", {}).items():
                result[key] = value.status

        except KeyError:
            logger.error("application id {} doesn't exist".format(app_id))
            raise KeyError
        return result

    def _cleanup(self, id, adaptors):
        """ method called by the engine to launch the celanup method of all the components for a specific application
        identified by it's ID, and removing the template from files/templates"""

        logger.info("cleaning up the file after undeployment")
        for step in self.object_config.step_config['cleanup']:
            try:
                adaptors[step].cleanup()
            except KeyError as e:
                logger.debug("{} not in initialised/translated adaptors, skipping...".format(e))
            except Exception as e:
                logger.error("error: {}; proceeding to cleanup of the other adaptors".format(e))


    def _update_json(self):
        """ method called by the engine to update the json file that will contain the dictionary of the IDs of the applications
        and the list of the IDs of its components link to the ID of the app.

        """
        data_to_save = dict()

        for key, value in self.app_list.items():
            data_to_save = {key: None}
            for k, v in self.app_list[key].items():
                logger.debug("key is: {} k is {} v is {}".format(key, k,v))
                if "components" in k or "outputs" in k:
                    data_to_save[key]={ k: v}
        if not data_to_save:
            logger.info("data to save is empty")
            data_to_save = {}


        try:
            with open(JSON_FILE, 'w') as outfile:
                json.dump(data_to_save, outfile)
        except Exception as e:
            logger.warning("{}".format(e))


    def _save_file(self, id_app, path):
        """ method called by the engine to dump the current template being treated to the files/templates directory, with as name
        the ID of the app.
        """
        data = utils.get_yaml_data(path)
        utils.dump_order_yaml(data, "files/templates/{}.yaml".format(id_app))
