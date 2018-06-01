#!/usr/bin/python

#from occopus.occopus import Occopus
from key_lists import KeyLists
from toscaparser.functions import GetInput
import logging
import utils
logger=logging.getLogger("submitter."+__name__)

class Mapper(object):
    """Mapper class that is modifying config dictionary"""
    def __init__(self, config, topology):

        logger.debug("in init of Mapper")

        self.topology = topology
        logger.debug("look for get_input in the template")
        self._find_get_input(topology.tpl)
            #self._orchestrator_selection()
        config.set_dictionary(topology)




    def _find_get_input(self,template):
        for key, value in template.items():
            if isinstance(value, dict):
                logger.debug("sub dictionary found, look through this to find \"get_input\"")
                result = self._find_get_input(value)
                if result is not None:
                    template[key] = self._get_input_value(result)
            elif isinstance(value, list):
                for i in value:
                    if isinstance(i, dict):
                        result = self._find_get_input(i)
                        if result is not None:
                            template[key][i] = self._get_input_value(result)
                    else:
                        logger.debug("this list doesn't contain any dictionary")
            elif isinstance(value, GetInput):
                logger.debug("GetInput object found, replace it with value")
                template[key] = self._get_input_value(value.input_name)

            elif "get_input" in key:
                return value

    def _get_input_value(self, key):
            try:
                if isinstance(self.topology.parsed_params, dict):
                    if self.topology.parsed_params[key]:
                        return self.topology.parsed_params[key]
            except KeyError as j:
                logger.error("{} no {} in parsed_params".format(j,key))

            try:
                logger.debug("ready to get the result")
                result=self._contains_inputs(self.topology.inputs, lambda x: x.name == key)

                return result.default
            except TypeError as e:
                logger.error("{}".format(e))


    def _contains_inputs(self, list_object, filter):
        logger.debug("check if inputs is in list")
        for i in list_object:
            if filter(i):
                return i
        return False
