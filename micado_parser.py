#!/usr/bin/python
from toscaparser.tosca_template import ToscaTemplate
import os
import toscaparser.utils.urlutils
import sys
import logging
import micado_validator as Validator

import inspect
import traceback

logger=logging.getLogger("submitter."+__name__)


class MiCADOParser(object):
  """
  MiCADO class that is going to take care of parsing the topology template, check if the
  file is correct and Readable by MiCADO submitter. The set_template method is returning
  the topology template object.
  """

  def __init__(self):
    """
    constructor, instantiate the class but doesn't do anything else.
    """
    logger.debug("Initialisation of the MiCADO Parser")

  def set_template(self,path, parsed_params=None):
    """
    set_template is the method that will parse the tosca template and return the
    object topology object.

    :params: path, parsed_params
    :type: string, dictionary
    :return: template
    :raises: Exception

    | parsed_params: dictionary containing the input to change
    | path: local or remote path to the file to parse (it needs to be reachable.)
    """
    self.path = path
    isfile = False
    if os.path.isfile(self.path):
      logger.debug("check if the input file is local")
      isfile = True
      #return ToscaTemplate(self.path, parsed_params, isfile)
    else:
      try:
        toscaparser.utils.urlutils.UrlUtils.validate_url(self.path)
        logger.debug("check if the input is a valid url")
        isfile = False
      except Exception as e:
        logger.error("the input file doesn't exist or cannot be reached")
        raise Exception("Cannot find input file {}".format(e))

    try:
        template = ToscaTemplate(self.path, parsed_params, isfile)
    except AttributeError as e:
        logger.error("error happened: {}, This might be due to the wrong type in the TOSCA template, check if all the type exist or that the import section is correct.".format(e))
        raise Exception("An error occured while parsing, This might be due to the a wrong type in the TOSCA template, check if all the types exist, or that the import section is correct.")


    Validator.validation(template)


    #    raise Exception("an error happened most likely with the policy, check if import section is right")

    return template
