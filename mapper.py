#!/usr/bin/python

#from occopus.occopus import Occopus
from key_lists import KeyLists
import logging
logger=logging.getLogger("submitter."+__name__)
class Mapper(object):
    """Mapper class that is creating a KeyList dictionnary"""
    def __init__(self, topology):
        logger.debug("in init of Mapper")
        self.topology = topology
        #self._orchestrator_selection()
        self.keylists = KeyLists(topology)
