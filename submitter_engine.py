from micado_parser import MiCADOParser
from mapper import Mapper
from plugins_gestion import PluginsGestion
import sys
from step import Step
from micado_validator import MultiError
from abstracts.exceptions import AdaptorCritical, AdaptorError
import utils
from key_lists import KeyLists
import json
import ruamel.yaml as yaml
import os
import time
from random import randint

import logging
""" set up of Logging """
LEVEL = logging.INFO
logging.basicConfig(filename="submitter.log", level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger=logging.getLogger("submitter."+__name__)

"""define the Handler which write message to sys.stderr"""
console = logging.StreamHandler()
console.setLevel(LEVEL)
""" set format which is simpler for console use"""
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')

console.setFormatter(formatter)

""" add the handler to the root logger"""
logging.getLogger('').addHandler(console)
logger.setLevel(LEVEL)

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
                logger.debug("instantiation of dictionary app_dict with {}".format(JSON_FILE))
                self.app_dict = json.load(json_data)
        except FileNotFoundError:
            logger.debug("file {} doesn't exist so isntantiation of empty directory of app_dict".format(JSON_FILE))
            self.app_dict = dict()

        self.adaptors_class_name = []
        self._get_adaptors_class()




    def launch(self, path_to_file, parsed_params=None):
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
        logger.info("Launching the application located there {}".format(path_to_file))
        template = self._micado_parser_upload(path_to_file, parsed_params)

        id_app = utils.id_generator()
        ids, object_adaptors = self._instantiate_adaptors(id_app, template)
        logger.debug("list of objects adaptor: {}".format(object_adaptors))
        #self._save_file(id_app, path_to_file)
        logger.debug("list of ids is: {}".format(ids))
        self.app_dict.update({id_app: ids})
        self._update_json()
        logger.info("dictionnaty of id is: {}".format(self.app_dict))

        self._engine(object_adaptors, template)
        return id_app

    def undeploy(self, id_app):
        """
        Undeploy method will remove the application from the infrastructure.
        :params: id
        :type: string
        """
        logger.info("proceding to the undeployment of the application")
        adaptors = self._instantiate_adaptors(id_app, app_ids=self.app_dict[id_app])
        logger.debug("{}".format(adaptors))
        try:
            for adaptor in reversed(adaptors):
                for item in self.app_dict[id_app]:
                    logger.debug("{}    {}".format(item, adaptor.__class__.__name__))
                    if adaptor.__class__.__name__ in item:

                        self._undeploy(adaptor)
        except KeyError as e:
            logger.error("no {} found in list of id".format(id_app))
            return
        self._cleanup(id_app, adaptors)
        self.app_dict.pop(id_app, None)
        self._update_json()



    def update(self, id_app, path_to_file, parsed_params):
        """
        Update method that will be updating the application we want to update.

        :params id: id of the application we want to update
        :params type: string

        :params path_to_file: path to the template file
        :params type: string

        :params parse_params: dictionary containing the value we want to use as the value of the input section
        :params type: dictionary

        """

        logger.info("proceding to the update of the application {}".format(id_app))
        template = self._micado_parser_upload(path_to_file, parsed_params)
        object_adaptors = self._instantiate_adaptors(id_app, template, self.app_dict[id_app])
        self._update(template, object_adaptors)

    def _engine(self,adaptors, template):
        """ Engine itself. Creates first a id, then parse the input file. Instantiate the
        mapper. Retreive the list of id created by the translate methods of the adaptors.
        Excute those id in their respective adaptor. Update the app_dict and the json file.
        """
        try:

            key_lists = self._mapper_instantiation(template)
            self._translate(adaptors)
            executed_adaptors = self._execute(adaptors)


        except MultiError as e:
            raise
        except AdaptorCritical as e:
            raise
        except AdaptorCritical as e:
            for adaptor in reversed(executed_adaptors):
                self._undeploy(adaptor, id_app)
            raise

    def _micado_parser_upload(self, path, parsed_params):
        """ Parse the file and retrieve the object """
        logger.debug("instantiation of submitter and retrieve template")
        parser = MiCADOParser()
        template= parser.set_template(path=path, parsed_params=parsed_params)
        logger.info("Valid & Compatible TOSCA template")
        return template


    def _mapper_instantiation(self, template):
        """ Retrieve the keylist from mapper """
        logger.debug("instantiation of mapper and retrieve keylists")
        mapper = Mapper(template)
        keylists = mapper.keylists
        return keylists

    def _get_adaptors_class(self):
        """ Retrieve the list of the differrent class adaptors """
        logger.debug("retreive the adaptors class")
        Keys=KeyLists().get_list_adaptors()
        PG=PluginsGestion()
        for k in Keys:
            adaptor = PG.get_plugin(k)
            logger.debug("adaptor found {}".format(adaptor))
            self.adaptors_class_name.append(adaptor)
        logger.debug("list of adaptors instantiated: {}".format(self.adaptors_class_name))

    def _instantiate_adaptors(self, app_id, template = None , app_ids = None):
        """ Instantiate the list of adaptors from the adaptors class list

            :params app_id: id of the application
            :params app_ids: list of ids to specify the adaptors (can be None)
            :params template: template of the application

            if provide list of adaptors object ids

            :returns: list of adaptors
            else if app_ids is None
            :returns: list of ids and list of adaptors object
        """
        adaptors = []

        if app_ids is None and template is not None:
            ids = []
            for adaptor in self.adaptors_class_name:
                logger.debug("instantiate {}".format(adaptor))
                obj = adaptor(template = template)
                ids.append("{}_{}_{}".format(app_id, obj.__class__.__name__, obj.ID))
                adaptors.append(obj)
            return ids, adaptors

        elif app_ids is not None and template is not None:
            ids = app_ids
            for adaptor in self.adaptors_class_name:
                for item in ids:
                    if adaptor.__name__ in items:
                        logger.debug("\n\n\nid: {}\n\n\n".format(item.split("_",2)))
                        adaptors.append(adaptor(template = template, adaptor_id = item.split("_",2)[2]))
        elif app_ids is not None and template is None:
            ids = app_ids
            for adaptor in self.adaptors_class_name:
                for item in ids:
                    if adaptor.__name__ in item:
                        logger.debug("\n\n\nid: {}\n\n\n".format(item.split("_",2)))
                        adaptors.append(adaptor(adaptor_id=item.split("_", 2)[2]))
            return adaptors


    def _translate(self, adaptors):
        """ Launch the translate engine """
        logger.debug("launch of translate method")
        logger.info("translate method called in all the adaptors")
        for adaptor in adaptors:
            logger.info("translating method call from {}".format(adaptor))
            while True:
                try:

                    Step(adaptor).translate()

                except AdaptorError as e:
                    continue
                break

    def _execute(self, adaptors):
        """ method called by the engine to launch the adaptors execute methods """
        logger.info("launch of the execute methods in each adaptors in a serial way")
        executed_adaptors = []
        for adaptor in adaptors:
                logger.debug("\t execute adaptor: {}".format(adaptor))
                Step(adaptor).execute()
        return executed_adaptors.append(adaptor)



    def _undeploy(self, adaptor):
        """ method called by the engine to launch the adaptor undeploy method of a specific component identified by its ID"""
        logger.info("undeploying component")
        Step(adaptor).undeploy()

    def _update(self, template, adaptors):
        """ method that will translate first the new component and then see if there's a difference, and then execute"""

    def _cleanup(self, id, adaptors):
        """ method called by the engine to launch the celanup method of all the components for a specific application
        identified by it's ID, and removing the template from files/templates"""

        logger.info("cleaning up the file after undeployment")
        for adaptor in reversed(adaptors):
            for item in self.app_dict[id]:
                if adaptor.__class__.__name__ in item:
                    Step(adaptor).cleanup()

    def _update_json(self):
        """ method called by the engine to update the json file that will contain the dictionary of the IDs of the applications
        and the list of the IDs of its components link to the ID of the app.

        """
        try:
            with open(JSON_FILE, 'w') as outfile:
                json.dump(self.app_dict, outfile)
        except Exception as e:
            logger.warning("{}".format(e))

    def _save_file(self, id_app, path):
        """ method called by the engine to dump the current template being treated to the files/templates directory, with as name
        the ID of the app.
        """
        data = utils.get_yaml_data(path)
        utils.dump_order_yaml(data, "files/templates/{}.yaml".format(id_app))
