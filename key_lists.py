#!/usr/bin/python
import yaml
KEYS = (OCCOPUS, DOCKER) = (["tosca.nodes.MiCADO.Occopus.CloudSigma.Compute", "tosca.nodes.MiCADO.Occopus.Nova.Compute","tosca.nodes.MiCADO.Occopus.CloudBroker.Compute","tosca.nodes.MiCADO.Occopus.EC2.Compute"], "tosca.nodes.MiCADO.Container.Application.Docker")

import collections
class KeyLists():
  def __init__(self, template):
      self.keys = dict()
      self.__set_dictionnary()
      self.__update_dictionnary(template)

  def __reading_config(self):
      dic_types=dict()
      with open("key_config.yml", 'r') as stream:
          try:
               dic_types=yaml.load(stream)
          except yaml.YAMLError as exc:
              print(exc)
      return dic_types

  def __set_dictionnary(self):
      tmp_dic=self.__reading_config()['key_config']
      for key, value in tmp_dic.iteritems():
          if isinstance(value, list):
              self.keys.setdefault(key)
              _interm_dict=dict()
              for type in value:
                  _interm_dict.setdefault(type)
              self.keys.__setitem__(key,_interm_dict)
          else:
              self.keys.setdefault(key)


  def __update_dictionnary(self, template):
      for node in template.nodetemplates:
          for inbeded_dict in self.keys:
              if self.__key_exist(inbeded_dict, node.type):
                  self.__update_embeded(node.type, node)

  def __update_embeded(self, key, value):
      for k, v in self.keys.iteritems():
          if k is key:
              self.keys[k]=value
          elif isinstance(v, collections.Mapping):
              for i in v:
                  if key in i and v[i] is None:
                      self.keys[k][i]=value
                  elif key in i and isinstance(v[i],list):
                      print v
                      _element = v[i]
                      _element.append(value)
                      self.keys[k][i]=_element
                  elif key in i and v[i] is not None:
                      print i
                      self.keys[k][i]=[v[i],value]


  def __key_exist(self, *keys_to_check):
      if type(self.keys) is not dict:
          raise AttributeError('self.keys is expected to be a dict')
      if len(keys_to_check) == 0:
          raise AttributeError('key is supposed to be non nul')
      _element= self.keys
      for key in keys_to_check:
          try:
              _element=_element[key]
          except KeyError:
              return False
      return True

  def get_KeyLists(self):
      return self.keys
  def get_cloud_orchestrator(self):
      return self.keys["cloud_orchestrator"]

  def get_container_orchestrator(self):
      return self.keys["container_orchestrator"]

  def get_security_enforcer(self):
      return self.keys["security_enforcer"]

  def get_policies_engine(self):
      return self.keys["policies_engine"]

  def get_node_from_type(self, type):
      for key, value in self.keys.iteritems():
          print key
          print type
          if key is type and not isinstance(value, collections.Mapping):
              print "not is instance"
              return value
          elif isinstance(value, collections.Mapping):
              print "is indeed instance"
              for k, v in value.iteritems():
                  if k in type:
                      return v


