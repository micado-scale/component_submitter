#!/usr/bin/python
#from toscaparser.shell import ToscaTemplate
import toscaparser
from toscaparser.tosca_template import ToscaTemplate
import os
import sys
import toscaparser.utils.urlutils
from system_prompt import Prompt
from occopus.occopus import Occopus


class Submitter:
  """Submitter class that is 


  going to take care of launching the application from TOSCA descriptor"""

  def __init__(self, path):
    self.path = path
    if os.path.isfile(self.path):
      template = ToscaTemplate(self.path, None, True)
    elif toscaparser.utils.urlutils.UrlUtils.validate_url(self.path):
      template = ToscaTemplate(self.path, None, False)
    self.template = template


  def inputs_prompt(self):
    if Prompt("keep all the default value?").query_yes_no():
      print "proceeding to the launch of the application\n"
      self.launch_application()
    elif Prompt("change all the default value?").query_yes_no():
      print "proceeding to update of default value\n"
      self.update_all_default()
    elif Prompt("input the value you want to modify"):
      print "updating the wanted input\n"
      self.update_inputs_value()

  def launch_application(self):
    occopus = Occopus(self.template)
    return occopus
  
  def update_all_default(self):
    print "entering of update value of inputs. Press enter if you want to keep default"
    for item in self.template.inputs:
      print "\n%s should be from %s" % (item.name, item.type)
      value = Prompt("update %s: " % item.name).query_input()

      if value is not None:
        self.template.tpl["topology_template"]["inputs"][item.name]["default"] = value      

  def list_inputs(self):
    for item in self.template.inputs:
      print "the value of %s is %s" % (item.name,item.default)

  def update_inputs_value(self):
    print "below list of inputs, type the one you would like to modify:\n"
    for item in self.template.inputs:
      print item.name

    while Prompt("\nwould you like to update an input value").query_yes_no():
      self.update_wanted_input_value()
        
  def update_wanted_input_value(self):
    wanted_input = Prompt("which one would you like to modify? ").query_input()
    for item in self.template.inputs:
      if wanted_input == item.name:
        self.template.tpl["topology_template"]["inputs"][item.name]["default"] = Prompt("%s :"% wanted_input).query_input()





