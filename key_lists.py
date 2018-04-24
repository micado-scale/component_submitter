#!/usr/bin/python
import yaml
import re
import collections
import logging
logger=logging.getLogger("submitter."+__name__)

CONFIG_FILE = "system/key_config.yml"

class KeyLists():
  def __init__(self):
      logger.debug("initialisation of KeyLists class")
      self.keys = dict()
      #self.template = template
      #self._set_dictionary()
      #self._update_dictionary()

  def get_list_adaptors(self):
      """return list of adaptors to use"""
      logger.debug("get the list of adaptors")
      adaptor_list=[]
      for key, value in self._reading_config()["key_config"].items():
          adaptor_list.append(key)

      logger.debug("adaptors:  {}".format(adaptor_list))
      return adaptor_list


  def _retrieve_custom_type(self, template):
      """list all the custom types"""

      logger.debug("retrieving custom type from tosca")
      list_custom_type=[]
      for key in template._get_all_custom_defs():
          list_custom_type.append(key)
      logger.debug("creation of list with custom type in it")
      return list_custom_type

  def _reading_config(self):
      """reading the config file and creating a dictionary related to it"""
      logger.debug("reading config file")
      dic_types=dict()
      with open(CONFIG_FILE, 'r') as stream:
          try:
               dic_types=yaml.load(stream)
          except yaml.YAMLError as exc:
              logger.error("Error while reading file, error: %s" % exc)
      logger.debug("return dictionary of types from config file")
      return dic_types

  def _check_re(self, key, template):
      """check the if the regular expression '*' return True or False"""
      logger.debug("check regular expression wild card")
      _list_custom = self._retrieve_custom_type(template)
      output = []
      if '*' in key:
          logger.debug("return True as * in key ")
          return True
      else:
          logger.debug("return False as no * in key")
          return False

  def _list_for_re(self, key, template):
      """return list of the correspondant types"""
      logger.debug("creation of list with correct type")
      _list_custom = self._retrieve_custom_type(template)
      output = []
      pattern = re.compile(key)
      for type in _list_custom:
          try:
              item = pattern.search(type)
              output.append(item.string)
          except AttributeError:
              pass
      return output



  def set_dictionary(self, template):
      """setting the dictionary, first going to call method to read config
        and implement the dictionary related to it."""
      logger.debug("set dictionary")
      tmp_dic=self._reading_config()['key_config']
      for key, value in tmp_dic.items():
          if isinstance(value, list):
              self.keys.setdefault(key)
              _interm_dict=dict()
              for type in value:
                  if self._check_re(type, template):
                      for t in self._list_for_re(type):
                          _interm_dict.setdefault(t)
                  else:
                      _interm_dict.setdefault(type)
              self.keys.__setitem__(key,_interm_dict)
          else:
              if self._check_re(key):
                  for type in self._list_for_re(key):
                      self.keys.setdefault(type)
              else:
                  self.keys.setdefault(key)
      self._update_dictionary(template)

  def _update_dictionary(self, template):
      """updating the dictionary with value related to the template"""
      logger.debug("update dictionary")
      for inbeded_dict in self.keys:
          for node in template.nodetemplates:
              if self._key_exist(inbeded_dict, node.type):
                  self._update_embeded(node.type, node, inbeded_dict)

  def _update_embeded(self, key, value, embeded):
      """methode to update the embedded dictionary"""
      logger.debug("update embedded dictionary")
      for k, v in self.keys.items():
          if k is embeded and isinstance(v, collections.Mapping):
              for i in v:
                  if key in i and v[i] is None:
                      self.keys[k][i]=value
                  elif key in i and isinstance(v[i],list):
                      _element = v[i]
                      _element.append(value)
                      self.keys[k][i]=_element
                  elif key in i and v[i] is not None:
                      self.keys[k][i]=[v[i],value]


  def _key_exist(self, *keys_to_check):
      """method to know if the key exist in the config file"""
      logger.debug("check if the key exist")
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
      """retrieve the whole dictionary"""
      logger.debug("get KeyList invoked")
      return self.keys

  def get_dict(self, key):
      """retrieve the dictionary wanted"""
      logger.debug("get dict invoked")
      return self.keys[key]

  def get_node_from_type(self, type):
      """retrieve wanted node through its type"""
      logger.debug("get node or nodes having type %s" % type)
      for key, value in self.keys.items():
          if key is type and not isinstance(value, collections.Mapping):
              return value
          elif isinstance(value, collections.Mapping):
              for k, v in value.items():
                  if k in type:
                      return v
