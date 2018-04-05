from micado_parser import MiCADOParser
from mapper import Mapper
from plugins_gestion import PluginsGestion
import sys
from step import Step

import logging

logging.basicConfig(filename="submitter.log", level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger=logging.getLogger("submitter."+__name__)

class SubmitterEngine(object):
    """docstring for SubmitterEngine."""
    def __init__(self, **kwargs):
        super(SubmitterEngine, self).__init__()
        logger.debug("init of submitter engine class")
        try:
            self.path = kwargs["path_to_file"]
        except KeyError as e:
            logger.error("\"path_to_file\" arg not found.")
            raise
        try:
          self.parsed_params = kwargs["parsed_params"]
        except KeyError as e:
          logger.warning("KeyError, no {} key detected, will be set to None".format(e))
        self.adaptors = []
        self.parsed_params = None
        self._micado_parser_upload()
        self._mapper_instantiation()
        self._instantiate_adaptors()
        self._translate()
        self._execute()


    def _micado_parser_upload(self):
        """parse the file and retrieve the object"""
        logger.debug("instantiation of submitter and retrieve template")
        parser = MiCADOParser()
        self.template= parser.set_template(path=self.path, parsed_params=self.parsed_params)

    def _mapper_instantiation(self):
        """retrieve the keylist from mapper"""
        logger.debug("instantiation of mapper and retrieve keylists")
        mapper = Mapper(self.template)
        self.keylists = mapper.keylists

    def _instantiate_adaptors(self):
        """instantiate the differrent adaptors"""
        logger.debug("instantiate the adaptors")
        Keys=self.keylists.get_KeyLists()
        PG=PluginsGestion()
        for k, v in Keys.items():
            adaptor = PG.get_plugin(k)
            logger.debug("adaptor found {}".format(adaptor))
            self.adaptors.append(adaptor)
        logger.debug("list of adaptors instantiated: {}".format(self.adaptors))

    def _translate(self):
        """launch the translate engine"""
        logger.debug("launch of translate method")
        logger.info("translate method called in all the adaptors")
        for adaptor in self.adaptors:
            logger.info("translating method call from {}".format(adaptor))
            adaptor.translate(self.template)

    def _execute(self):
        """launch the execution engine"""
        logger.info("launch of the execute methods in each adaptors in a serial way")
        for adaptor in self.adaptors:
            logger.debug("\t execute adaptor: {}".format(adaptor))
            Step(adaptor)
