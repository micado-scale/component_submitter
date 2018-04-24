from micado_parser import MiCADOParser
from mapper import Mapper
from plugins_gestion import PluginsGestion
import sys
from step import Step
from micado_validator import MultiError
from abstracts.exceptions import AdaptorCritical, AdaptorError
import logging
import generator
from key_lists import KeyLists
import json


JSON_FILE = "system/ids.json"
LEVEL = "INFO"
logging.basicConfig(filename="submitter.log", level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger=logging.getLogger("submitter."+__name__)
logger.setLevel(LEVEL)
class SubmitterEngine(object):
    """ SubmitterEngine class that is the main one that is used to treat with the application. """
    def __init__(self, **kwargs):
        """
        instantiate the SubmitterEngine class. Creating empty list for the whole class
        adaptor and executed adaptor. launching the execute method.
        """
        super(SubmitterEngine, self).__init__()
        logger.debug("init of submitter engine class")
        self.adaptors = []
        self.executed_adaptors = []
        self.parsed_params = None
        self.e = None

        try:
            with open(JSON_FILE, 'r') as json_data:
                logger.debug("instantiation of dictionary id_dict with {}".format(JSON_FILE))
                self.id_dict = json.load(json_data)
        except FileNotFoundError:
            logger.debug("file {} doesn't exist so isntantiation of empty directory of id_dict".format(JSON_FILE))
            self.id_dict = dict()

        try:
            self.path = kwargs["path_to_file"]
        except KeyError as e:
            logger.error("\"path_to_file\" arg not found.")
            raise
        try:
          self.parsed_params = kwargs["parsed_params"]
        except KeyError as e:
          logger.warning("KeyError, no {} key detected, will be set to None".format(e))

        self._instantiate_adaptors()
        logger.debug("{}".format(self.adaptors))
        self._engine()
        #self._translate()
        #self._execute()

    def undeploy(self, id_app):
        """
        undeploy method will remove the application from the infrastructure.
        :params: id
        :type: string

        this method needs to be implemented
        """
        logger.info("proceding to the undeployment of the application")
        try:
            for adaptor in reversed(self.executed_adaptors):
                for item in self.id_dict[id_app]:
                    if adaptor.__class__.__name__ in item:
                        self._undeploy(adaptor, item.split("_",1)[1])
        except KeyError as e:
            logger.error("no {} found in list of id".format(id_app))
            return
        self.id_dict.pop(id_app, None)
        self._update_json()


    def _engine(self):
        """ Engine itself. Creates first a id, then parse the input file. Instantiate the
        mapper. Retreive the list of id created by the translate methods of the adaptors.
        Excute those id in their respective adaptor. Update the id_dict and the json file.
        """
        try:
            id_app=generator.id_generator()

            self._micado_parser_upload()
            self._mapper_instantiation()
            id_list=self._translate()
            self._execute(id_list)
            self.id_dict.update({id_app: id_list})
            self._update_json()
            logger.info("dictionnaty of id is: {}".format(self.id_dict))


        except MultiError as e:
        #    self._inform_user(e, e.levelname)
            raise
        except AdaptorCritical as e:
        #    self._inform_user(e, e.levelname)
            raise
        except AdaptorCritical as e:
            for adaptor in reversed(self.executed_adaptors):
                self._undeploy(adaptor)
        #    self._inform_user(e, e.levelname)
            raise

    def _micado_parser_upload(self):
        """ Parse the file and retrieve the object """
        logger.debug("instantiation of submitter and retrieve template")
        parser = MiCADOParser()
        self.template= parser.set_template(path=self.path, parsed_params=self.parsed_params)
        logger.info("Valid & Compatible TOSCA template")

    def _mapper_instantiation(self):
        """ Retrieve the keylist from mapper """
        logger.debug("instantiation of mapper and retrieve keylists")
        mapper = Mapper(self.template)
        self.keylists = mapper.keylists

    def _instantiate_adaptors(self):
        """ Instantiate the differrent adaptors """
        logger.debug("instantiate the adaptors")
        Keys=KeyLists().get_list_adaptors()
        PG=PluginsGestion()
        for k in Keys:
            adaptor = PG.get_plugin(k)
            logger.debug("adaptor found {}".format(adaptor))
            self.adaptors.append(adaptor)
        logger.debug("list of adaptors instantiated: {}".format(self.adaptors))

    def _translate(self):
        """ Launch the translate engine """
        logger.debug("launch of translate method")
        ids=[]
        logger.info("translate method called in all the adaptors")
        for adaptor in self.adaptors:
            logger.info("translating method call from {}".format(adaptor))
            while True:
                try:
                    ids.append("{}_{}".format(adaptor.__class__.__name__,Step(adaptor).translate(self.template)))
                except AdaptorError as e:
                    continue
                break
        return ids
        #    adaptor.translate(self.template)
    def _execute(self, ids):
        """ method called by the engine to launch the adaptors execute methods """
        logger.info("launch of the execute methods in each adaptors in a serial way")
        for adaptor in self.adaptors:
            for i in ids:
                if adaptor.__class__.__name__ in i:
                    logger.debug("\t execute adaptor: {}".format(adaptor))
                    Step(adaptor).execute(i.split("_",1)[1])
            self.executed_adaptors.append(adaptor)



    def _undeploy(self, adaptor, id):
        """ method called by the engine to launch the adaptor undeploy method of a specific component identified by its ID"""
        logger.info("undeploying component")
        Step(adaptor).undeploy(id)

    #def _inform_user(self, message, level):
    #    """ Give the User the infromation on what happened """
    #    if "CRITICAL" in level:
    #        logger.critical(message)
    #    elif "INFO" in level:
    #        logger.info(message)
    #    elif "DEBUG" in level:
    #        logger.debug(message)
    #    elif "ERROR" in level:
    #        logger.error(message)

    def _update_json(self):
        try:
            with open(JSON_FILE, 'w') as outfile:
                json.dump(self.id_dict, outfile)
        except Exception as e:
            logger.warning("{}".format(e))
