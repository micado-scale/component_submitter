"""
MiCADO Submitter Engine Submitter Config
----------------------------------------
A module allowing the configuration of the whole submitter
"""
import ruamel.yaml as yaml
import logging
from os import path

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
        self.config_path = testing or CONFIG_FILE
        config = self._reading_config()
        
        self.main_config = config["main_config"]
        self.step_config = config["step"]
        self.logging_config = config["logging"]
        self.adaptor_config = config["adaptor_config"]

    def get_list_adaptors(self):
        """return list of adaptors to use"""
        logger.debug("get the list of adaptors")
        adaptor_list = []
        for key, value in self._reading_config()["adaptor_config"].items():
            adaptor_list.append(key)

        logger.debug("adaptors:  {}".format(adaptor_list))
        return adaptor_list

    def _reading_config(self):
        """reading the config file and creating a dictionary related to it"""
        logger.debug("reading config file")
        dic_types = dict()
        yaml.default_flow_style = False
        with open(self.config_path, "r") as stream:
            try:

                dic_types = yaml.round_trip_load(
                    stream.read(), preserve_quotes=True
                )
            except OSError as exc:

                logger.error("Error while reading file, error: %s" % exc)
        logger.debug("return dictionary of types from config file")
        return dic_types

    def resolve_inputs(self, template):
        self._find_get_input(template.tpl, template)
        
    def _find_get_input(self, tpl, template):
        for key, value in tpl.items():
            if key == "get_input":
                return value
            elif isinstance(value, dict):
                result = self._find_get_input(value, template)
                if result:
                    tpl[key] = self._get_input_value(result, template)
            elif isinstance(value, list):
                for i in value:
                    if not isinstance(i, dict):
                        continue
                    result = self._find_get_input(i, template)
                    if result:
                        tpl[key][i] = self._get_input_value(result, template)

    def _get_input_value(self, key, template):
        try:
            return template.parsed_params[key]
        except (KeyError, TypeError):
            logger.debug(f"Input '{key}' not given, using default")

        try:
            return [
                param.default for param
                in template.inputs
                if param.name == key][0]
        except IndexError:
            logger.error(f"Input '{key}' has no default")

