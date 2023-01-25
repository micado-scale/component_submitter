"""
MiCADO Submitter Engine Submitter Config
----------------------------------------
A module allowing the configuration of the whole submitter
"""
import logging
from os import path

from submitter import utils

basepath = path.dirname(__file__)
CONFIG_FILE = "{}/system/key_config.yml".format(basepath)

logger = logging.getLogger("submitter." + __name__)


class SubmitterConfig:
    """
    This is the SubmitterConfig,
    in charge of the configuration of the whole submitter.
    It has ``__init__()``, ``get_list_adaptors()``,
    ``_reading_config()``, ``_find_get_input()``,
    ``get_SubmitterConfig()``, ``get_dict()`` and ``get_node_from_type()``.

    Optional testing parameter can be passed to __init__
    to define which key_config files to take for test purposes.


    """

    def __init__(self, testing=None):
        logger.debug("initialisation of SubmitterConfig class")
        config_path = testing or CONFIG_FILE
        config = _reading_config(config_path)

        self.main_config = config["main_config"]
        self.step_config = config["step"]
        self.logging_config = config["logging"]
        self.adaptor_config = config["adaptor_config"]

    def get_list_adaptors(self):
        """return list of adaptors to use"""
        logger.debug("get the list of adaptors")
        return [adaptor for adaptor in self.adaptor_config]

def _reading_config(path):
    """reading the config file and creating a dictionary related to it"""
    logger.debug("reading config file")
    return utils.get_yaml_data(path)
