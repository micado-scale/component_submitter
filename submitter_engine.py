from micado_parser import MiCADOParser
from mapper import Mapper
from plugins_gestion import PluginsGestion
import sys
from step import Step
from micado_validator import MultiError
from abstracts.exceptions import AdaptorCritical
import logging

logging.basicConfig(filename="submitter.log", level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger=logging.getLogger("submitter."+__name__)

class SubmitterEngine(object):
    """ Docstring for SubmitterEngine. """
    def __init__(self, **kwargs):
        super(SubmitterEngine, self).__init__()
        logger.debug("init of submitter engine class")
        self.adaptors = []
        self.executed_adaptors = []
        self.parsed_params = None
        try:
            self.path = kwargs["path_to_file"]
        except KeyError as e:
            logger.error("\"path_to_file\" arg not found.")
            raise
        try:
          self.parsed_params = kwargs["parsed_params"]
        except KeyError as e:
          logger.warning("KeyError, no {} key detected, will be set to None".format(e))

        self._engine()
        #self._translate()
        #self._execute()

    def _engine(self):
        """ Engine itself """
        self._micado_parser_upload()
        self._mapper_instantiation()
        try:
            self._instantiate_adaptors()
        except AdaptorCritical as e:
            if e is AdaptorCritical:
                self._inform_user(e)

        try:
            self._translate()
        except AdaptorCritical as e:
            if e is AdaptorCritical:
                self._inform_user(e)
        try:
            self._execute()
        except AdaptorCritical as e:
            for adaptor in reversed(self.executed_adaptors):
                self._undeploy(adaptor)
            self._inform_user(e)

    def _micado_parser_upload(self):
        """ Parse the file and retrieve the object """
        logger.debug("instantiation of submitter and retrieve template")
        parser = MiCADOParser()
        try:
            self.template= parser.set_template(path=self.path, parsed_params=self.parsed_params)
        except MultiError as e:
            logger.error(e.msg)
            exit(1)

    def _mapper_instantiation(self):
        """ Retrieve the keylist from mapper """
        logger.debug("instantiation of mapper and retrieve keylists")
        mapper = Mapper(self.template)
        self.keylists = mapper.keylists

    def _instantiate_adaptors(self):
        """ Instantiate the differrent adaptors """
        logger.debug("instantiate the adaptors")
        Keys=self.keylists.get_KeyLists()
        PG=PluginsGestion()
        for k, v in Keys.items():
            adaptor = PG.get_plugin(k)
            logger.debug("adaptor found {}".format(adaptor))
            self.adaptors.append(adaptor)
        logger.debug("list of adaptors instantiated: {}".format(self.adaptors))

    def _translate(self):
        """ Launch the translate engine """
        logger.debug("launch of translate method")
        logger.info("translate method called in all the adaptors")
        for adaptor in self.adaptors:
            logger.info("translating method call from {}".format(adaptor))
            Step(adaptor).translate(self.template)
        #    adaptor.translate(self.template)
    def _execute(self):
        """ Launch the execution engine """
        logger.info("launch of the execute methods in each adaptors in a serial way")
        for adaptor in self.adaptors:
            logger.debug("\t execute adaptor: {}".format(adaptor))
            Step(adaptor).execute()
            self.executed_adaptors.append(adaptor)


    def _undeploy(self, adaptor):
        """ Undeploy component """
        logger.info("undeploying component")
        Step(adaptor).undeploy()

    def _inform_user(self, message):
        """ Give the User the infromation on what happened """
        # TODO: store the message for after run is stopped.
        print("message should be delivered if requested through API")
        print(message)
        print("should exit")
