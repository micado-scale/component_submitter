#!/usr/bin/python
from toscaparser.tosca_template import ToscaTemplate
from toscaparser.common.exception import ValidationError
import os
import toscaparser.utils.urlutils
import sys
import logging
import micado_validator as Validator

import inspect
import traceback

logger = logging.getLogger("submitter." + __name__)


def set_template(path, parsed_params=None):
    """ the method that will parse the YAML and return ToscaTemplate
    object topology object.

    :params: path, parsed_params
    :type: string, dictionary
    :return: template
    :raises: Exception

    | parsed_params: dictionary containing the input to change
    | path: local or remote path to the file to parse
    """
    isfile = _isfile_check(path)

    try:
        template = ToscaTemplate(path, parsed_params, isfile)
    except ValidationError as e:
        message = [
            line
            for line in e.message.splitlines()
            if not line.startswith("\t\t")
        ]
        message = "\n".join(message)
        raise Exception(message) from None
    except AttributeError as e:
        logger.error(
            f"error happened: {e}, This might be due to the wrong type in "
            "the TOSCA template, check if all the type exist or that the "
            "import section is correct."
        )
        raise Exception(
            "An error occured while parsing, This might be due to the a "
            "wrong type in the TOSCA template, check if all the types "
            "exist, or that the import section is correct."
        ) from None

    Validator.validation(template)
    return template


def _isfile_check(path):
    if os.path.isfile(path):
        logger.debug("check if the input file is local")
        return True

    logger.debug("checking if the input is a valid url")
    try:
        toscaparser.utils.urlutils.UrlUtils.validate_url(path)
        return False
    except Exception as e:
        logger.error("the input file doesn't exist or cannot be reached")
        raise Exception("Cannot find input file {}".format(e))