#!/usr/bin/python

KEYS = (OCCOPUS, DOCKER) = (["tosca.nodes.MiCADO.Occopus.CloudSigma.Compute", "tosca.nodes.MiCADO.Occopus.Nova.Compute","tosca.nodes.MiCADO.Occopus.CloudBroker.Compute","tosca.nodes.MiCADO.Occopus.EC2.Compute"], "tosca.nodes.MiCADO.Container.Application.Docker")
class KeyLists():

  def __init__(self, template):
      self.keys=dict()
      self._creation_empty_dictionnary()
      self._update_dictionnary(template)

  def _creation_empty_dictionnary(self):
      for orchestrator in KEYS:
          if isinstance(orchestrator, list):
              for type in orchestrator:
                  self.keys.setdefault(type)
          else:
              self.keys.setdefault(orchestrator)


  def _update_dictionnary(self, template):
      for node in template.nodetemplates:
          if node.type in self.keys:
              if self.keys.__getitem__(node.type) is not None:
                  _element=[]
                  if isinstance(self.keys.__getitem__(node.type),list):
                      _element=self.keys.__getitem__(node.type)
                  else:
                      _element=[self.keys.__getitem__(node.type)]
                  _element.append(node)
                  self.keys.__setitem__(node.type,_element)
              else:
                  self.keys.__setitem__(node.type,node)




 # def _orchestrator_selection(self):
  #    orchestrators = []
  #    nodes = self.topology.nodetemplates
  #    self.orchestrator = None
  #    for node in nodes:
  #        if OCCOPUS in node.type:
  #            orchestrators.append(Occopus(node))
  #    return orchestrators


 # def _get_container_manager(self):
 #     container_orchestrator = []
 #     nodes = self.topology.nodetemplates
 #     for node in nodes:
 #         if DOCKER in node.type:
 #           container_orchestrator.append(DOCKER)



