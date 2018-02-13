#!/user/bin/python

from cloudsigma import CloudSigma
from ec2 import EC2
import yaml

class Occopus:

  def __init__(self, template):
    self.template = template
    self.occopus_api_call()
#
  def resource_type(self):
    _template = self.template
    cloud = ""
    if "tosca.nodes.MiCADO.Occopus.CloudSigma.Compute" in _template.type:
     # self.cloudsigma_resource(self.template)
      cloud=CloudSigma(_template)

    print cloud
    return cloud.file()
    
 # def __get_compute_node(self):
 #   nodes = []
 #   for node in self.template.nodetemplates:
 #     if "Occopus" in node.type or "occopus" in node.type:
 #       nodes.append(node)
 #   return nodes



 # def __instance_to_launch(self):
 #   instances = []
 #   for node in self.__get_compute_node():
 #     if "CloudSigma" in node.type:
 #       instances.append(CloudSigma(node))
 #   return instances


 # def occopus_api_call(self):
 #   instances = self.__instance_to_launch()
 #   for instance in instances:
 #     occopus_file = instance.file()
 #     with open('data.yml', 'w') as outfile:
 #       yaml.dump(data, outfile, default_flow_style=False)

  def occopus_api_call(self):
    occopus_file = self.resource_type()
    print occopus_file
    with open('data.yml','w') as outfile:
      yaml.dump(occopus_file, outfile,default_flow_style=False)
