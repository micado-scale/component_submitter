#!/usr/bin/python

#from occopus.occopus import Occopus
from key_lists import KeyLists
import logging
from toscaparser.functions import GetInput
logger=logging.getLogger("submitter."+__name__)
class Mapper(object):
    """Mapper class that is creating a KeyList dictionnary"""
    def __init__(self, topology):
        logger.debug("in init of Mapper")
        self.topology = topology
        self._look_for_get_input()
        #self._orchestrator_selection()
        self.keylists = KeyLists(topology)


    def _look_for_get_input(self):
        logger.debug("look for get_input in the template")
        self._find_get_input_in_dict(self.topology.tpl["topology_template"]["node_templates"])

    def _find_get_input_in_dict(self,template):
        for key, value in template.items():
            if isinstance(value,dict):
                logger.debug("sub dictionnary found, look through this to find \"get_iput\"")
                result = self._find_get_input_in_dict(value)
                if result is not None:
                    logger.debug("\"get_input\" found replace it with value")
                    template[key] = self._get_input_value(result)
            elif isinstance(value, list):
                logger.debug("list found, look through this to find \"get_iput\"")
                for i in value:
                    result = self._find_get_input_in_dict(i)
                    if result is not None:
                        logger.debug("\"get_input\" found replace it with value")
                        template[key][i] = self._get_input_value(result)

            elif isinstance(value, GetInput):
                logger.debug("GetInput object found, replace it with value")
                template[key] = self._get_input_value(value.input_name)

            elif "get_input" in key:
                return value

    def _get_input_value(self, key):
            try:
                if isinstance(self.topology.parsed_params, dict):
                    if self.topology.parsed_params[key]:
                        return self.topology.parsed_params
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
