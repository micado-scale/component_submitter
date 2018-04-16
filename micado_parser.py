#!/usr/bin/python
from toscaparser.tosca_template import ToscaTemplate
import os
import toscaparser.utils.urlutils
import sys
import logging
from micado_validator import Validator, MultiError
logger=logging.getLogger("submitter."+__name__)


class MiCADOParser(object):
  """Submitter class that is
  going to take care of launching the application from TOSCA descriptor"""

  def __init__(self):
    logger.debug("Initialisation of the MiCADO Parser")

  def set_template(self,path, parsed_params=None):
    """set template that will parse the tosca template and return a template."""
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

    template = ToscaTemplate(self.path, parsed_params, isfile)
    Validator(template)

    return template
