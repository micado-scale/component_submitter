#!/usr/bin/python
ORCHESTARTOR = (OCCOPUS) = ('Occopus')
CONTAINER  = (DOCKER) = ('Docker')

from occopus.occopus import Occopus


class Mapper(object):
    def __init__(self, topology):
        self.topology = topology
        self._orchestrator_selection()
    ## selection of the orchestrator
    ## return a list of orchestrator to use

    def _orchestrator_selection(self):
        orchestrators=[]
        nodes = self.topology.nodetemplates
        self.orchestrator = None
        for node in nodes:
           if OCCOPUS in node.type:
             orchestrators.append(Occopus(node))
        return orchestrators

    def _get_container_manager(self):
        container_orchestrator = []
        nodes = self.topology.nodetemplates
        for node in nodes:
            if DOCKER in node.type:
                container_orchestrator.append(DOCKER)

