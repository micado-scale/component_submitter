"""
MiCADO Submitter Engine Submitter Config
----------------------------------------
A module allowing the configuration of the whole submitter
"""
import ruamel.yaml as yaml
import re
import collections
import utils
from os import path

basepath = path.dirname(__file__)
CONFIG_FILE = "{}/system/key_config.yml".format(basepath)
from toscaparser.functions import GetInput

import logging

logger = logging.getLogger("submitter." + __name__)


class SubmitterConfig:
    """
        This is the SubmitterConfig,
        in charge of the configuration of the whole submitter.
        It has ``__init__()``, ``get_list_adaptors()``, ``_retrieve_custom_type()``,
        ``_reading_config()``, ``_check_re()``, ``_list_for_re()``, ``mapping()``,
        ``_look_through_template()``, ``_find_get_input()``, ``_contains_inputs()``,
        ``get_SubmitterConfig()``, ``get_dict()`` and ``get_node_from_type()``.

        Optional testing parameter can be passed to __init__ to define which key_config files
        to take for test purposes.

        
  """

    def __init__(self, testing=None):
        logger.debug("initialisation of SubmitterConfig class")
        if testing:
            self.config_path = testing
        else:
            self.config_path = CONFIG_FILE
        config = self._reading_config()
        self.main_config = config["main_config"]
        self.step_config = config["step"]
        self.logging_config = config["logging"]
        self.mapping()

    def get_list_adaptors(self):
        """return list of adaptors to use"""
        logger.debug("get the list of adaptors")
        adaptor_list = []
        for key, value in self._reading_config()["adaptor_config"].items():
            adaptor_list.append(key)

        logger.debug("adaptors:  {}".format(adaptor_list))
        return adaptor_list

    def _retrieve_custom_type(self, template):
        """list all the custom types"""

        logger.debug("retrieving custom type from tosca")
        list_custom_type = []
        for key in template._get_all_custom_defs():
            list_custom_type.append(key)
        logger.debug("creation of list with custom type in it")
        return list_custom_type

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

    def _check_re(self, key, template):
        """check the if the regular expression '*' return True or False"""
        logger.debug("check regular expression wild card")
        _list_custom = self._retrieve_custom_type(template)
        output = []
        if "*" in key:
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

    def mapping(self, template=None):
        if template:
            self._find_get_input(template.tpl, template)
        logger.debug("set dictionary")
        tmp_dic = self._reading_config()["adaptor_config"]
        for key, value in tmp_dic.items():
            if isinstance(value, dict) and template is not None:
                for key_inter, value_inter in value.items():
                    _for_dic = dict()
                    if "types" in key_inter and isinstance(value_inter, list):
                        _list_inter = list()
                        for item in value_inter:
                            if self._check_re(item, template):
                                for item_inter in self._list_for_re(
                                    item, template
                                ):
                                    logger.debug(
                                        "item_inter {}".format(item_inter)
                                    )
                                    obj = self._look_through_template(
                                        item_inter, template
                                    )
                                    logger.debug("\t\tobject: {}".format(obj))
                                    if obj is not None:
                                        _list_inter.append({item_inter: obj})
                            else:
                                obj = self._look_through_template(
                                    item, template
                                )
                                if obj is not None:
                                    _list_inter.append({item: obj})
                        if _list_inter:
                            _for_dic[key_inter] = _list_inter
                            tmp_dic[key] = _for_dic
                    else:
                        tmp_dic[key][key_inter] = value_inter

            elif isinstance(value, dict) and template is None:
                for key_inter, value_inter in value.items():
                    _for_dic = dict()
                    if "types" in key_inter and isinstance(value_inter, list):
                        _list_inter = list()
                        for item in value_inter:
                            _list_inter.append(item)
                        logger.debug("key_inter is: {}".format(_list_inter))
                        _for_dic[key_inter] = _list_inter
                        # _for_dic['dry_run'] = self.main_config['dry_run']
                        tmp_dic[key] = _for_dic
                    else:
                        tmp_dic[key][key_inter] = value_inter

        logger.debug("the config is: {}".format(tmp_dic))
        self.adaptor_config = tmp_dic

    def _look_through_template(self, key, template):
        """look through template"""
        logger.debug("update dictionary")
        for node in template.nodetemplates:
            if key in node.type:
                return node
        for policy in template.policies:
            if key in policy.type:
                return policy
        return None

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

