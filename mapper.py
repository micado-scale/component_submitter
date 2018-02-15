#!/usr/bin/python
ORCHESTARTOR = (OCCOPUS) = ('Occopus')
CONTAINER  = (DOCKER) = ('Docker')

#from occopus.occopus import Occopus
from key_lists import KeyLists

class Mapper(object):
    def __init__(self, topology):
        self.topology = topology
        #self._orchestrator_selection()
    ## selection of the orchestrators.
    ## return a list of orchestrator to use




