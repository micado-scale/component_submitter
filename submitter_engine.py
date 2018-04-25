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

""" set up of Logging """
LEVEL = logging.DEBUG
logging.basicConfig(filename="submitter.log", level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger=logging.getLogger("submitter."+__name__)

logger.setLevel(LEVEL)
"""define the Handler which write message to sys.stderr"""
console = logging.StreamHandler()
console.setLevel(LEVEL)
""" set format which is simpler for console use"""
formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')

console.setFormatter(formatter)

""" add the handler to the root logger"""
logging.getLogger('').addHandler(console)

class SubmitterEngine(object):
    """ SubmitterEngine class that is the main one that is used to treat with the application. """
    def __init__(self):
        """
        instantiate the SubmitterEngine class. Creating empty list for the whole class
        adaptor and executed adaptor. launching the execute method.
        """
        super(SubmitterEngine, self).__init__()
        logger.debug("init of submitter engine class")
        self.adaptors = []

        try:
            with open(JSON_FILE, 'r') as json_data:
                logger.debug("instantiation of dictionary id_dict with {}".format(JSON_FILE))
                self.id_dict = json.load(json_data)
        except FileNotFoundError:
            logger.debug("file {} doesn't exist so isntantiation of empty directory of id_dict".format(JSON_FILE))
            self.id_dict = dict()


        self._instantiate_adaptors()
        logger.debug("{}".format(self.adaptors))



    def launch(self, path_to_file, parsed_params=None):
        """
        Launch method, that will call the in-method egine to execute the application
        :params: path_to_file, parsed_params
        :types: string, dictionary

        .. note::
            For the time being we only have one "workflow engine" but we could extend this
            launch method to accept another parameter to be able to choose which engine to
            launch
        """
        logger.info("Launching the application located there {}".format(path_to_file))

        id_app = self._engine(path_to_file, parsed_params)
        return id_app

    def undeploy(self, id_app):
        """
        Undeploy method will remove the application from the infrastructure.
        :params: id
        :type: string
        """
        logger.info("proceding to the undeployment of the application")
        try:
            for adaptor in reversed(self.adaptors):
                for item in self.id_dict[id_app]:
                    if adaptor.__class__.__name__ in item:
                        self._undeploy(adaptor, item.split("_",1)[1])
        except KeyError as e:
            logger.error("no {} found in list of id".format(id_app))
            return
        self._cleanup(id_app)
        self.id_dict.pop(id_app, None)
        self._update_json()




    def _engine(self, path, parsed_params):
        """ Engine itself. Creates first a id, then parse the input file. Instantiate the
        mapper. Retreive the list of id created by the translate methods of the adaptors.
        Excute those id in their respective adaptor. Update the id_dict and the json file.
        """
        try:
            id_app=generator.id_generator()

            template = self._micado_parser_upload(path, parsed_params)
            key_lists = self._mapper_instantiation(template)
            id_list=self._translate(template)
            logger.debug("list of ids is: {}".format(id_list))
            executed_adaptors = self._execute(id_list)
            self.id_dict.update({id_app: id_list})
            self._update_json()
            logger.info("dictionnaty of id is: {}".format(self.id_dict))


        except MultiError as e:
            raise
        except AdaptorCritical as e:
            raise
        except AdaptorCritical as e:
            for adaptor in reversed(executed_adaptors):
                self._undeploy(adaptor, id_app)
            raise
        return id_app

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

    def _translate(self, template):
        """ Launch the translate engine """
        logger.debug("launch of translate method")
        ids=[]
        logger.info("translate method called in all the adaptors")
        for adaptor in self.adaptors:
            logger.info("translating method call from {}".format(adaptor))
            while True:
                try:
                    ids.append("{}_{}".format(adaptor.__class__.__name__,Step(adaptor).translate(template)))
                except AdaptorError as e:
                    continue
                break
        return ids
        #    adaptor.translate(self.template)
    def _execute(self, ids):
        """ method called by the engine to launch the adaptors execute methods """
        logger.info("launch of the execute methods in each adaptors in a serial way")
        executed_adaptors = []
        for adaptor in self.adaptors:
            for i in ids:
                if adaptor.__class__.__name__ in i:

                    logger.debug("\t execute adaptor: {}".format(adaptor))
                    Step(adaptor).execute(i.split("_",1)[1])
        return executed_adaptors.append(adaptor)



    def _undeploy(self, adaptor, id):
        """ method called by the engine to launch the adaptor undeploy method of a specific component identified by its ID"""
        logger.info("undeploying component")
        Step(adaptor).undeploy(id)

    def _cleanup(self, id):
        logger.info("cleaning up the file after undeployment")
        for adaptor in reversed(self.adaptors):
            for item in self.id_dict[id]:
                if adaptor.__class__.__name__ in item:
                    Step(adaptor).cleanup(item.split("_",1)[1])


    def _update_json(self):
        try:
            with open(JSON_FILE, 'w') as outfile:
                json.dump(self.id_dict, outfile)
        except Exception as e:
            logger.warning("{}".format(e))
