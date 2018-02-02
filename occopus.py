#!/user/bin/python

class Occopus:

  def __init__(self, template):
    self.template = template

  def resource_type(self, node):
    if node.type is "tosca.nodes.MiCADO.Occopus.CloudSigma.Compute":
      self.cloudsigma_resource(node)

    

  def cloudsigma_resource(self):
    capabilities = node.entity_tpl['capabilities']["host"]


  def occopus_api_call(self, topology_template):
    template =  topology_template
    for node in template.nodetemplates:
      if "Compute" in node.type:
        print "This node is to define the Resource"
        compute_node = node
        print node
      else:
        print "This node is not belonging to the Resource definition"
