#!/user/bin/python

from cloudsigma import CloudSigma
class Occopus:

  def __init__(self, template):
    self.template = template

  def resource_type(self, node):
    if node.type is "tosca.nodes.MiCADO.Occopus.CloudSigma.Compute":
      self.cloudsigma_resource(node)

    
  def __get_compute_node(self):
    nodes = []
    for node in self.template.nodetemplates:
      if "Occopus" in node.type or "occopus" in node.type:
        nodes.append(node)
    return nodes

  def __selection_cloud(self):
    instances = []
    for node in self.__get_compute_node():
      if "CloudSigma" in node.type:
        instances.append(CloudSigma(node))
    return instances



 # def __get_input(self, name):
 #   inputs =  self.template.inputs
 #   for input in inputs:
  #    if name in input.name:
  #      return input.default


  def occopus_api_call(self, topology_template):
    template =  topology_template
    for node in template.nodetemplates:
      if "Compute" in node.type:
        print "This node is to define the Resource"
        compute_node = node
        print node
      else:
        print "This node is not belonging to the Resource definition"
