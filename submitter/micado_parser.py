import os
import sys
import logging
import inspect
import traceback
import urllib
import copy
import tempfile

import ruamel.yaml as yaml
import toscaparser.utils.urlutils
from toscaparser.tosca_template import ToscaTemplate
from toscaparser.common.exception import ValidationError

from submitter import micado_validator as Validator
from submitter.utils import resolve_get_inputs

logger = logging.getLogger("submitter." + __name__)


def set_template(path, parsed_params=None):
    """the method that will parse the YAML and return ToscaTemplate
    object topology object.

    :params: path, parsed_params
    :type: string, dictionary
    :return: template
    :raises: Exception

    | parsed_params: dictionary containing the input to change
    | path: local or remote path to the file to parse
    """
    yaml_dict = _get_dict(path)
    _resolve_occurrences(yaml_dict, parsed_params)

    template = get_template(parsed_params, yaml_dict)

    Validator.validation(template)
    _find_other_inputs(template)
    return template


def get_template(parsed_params, yaml_dict):
    try:
        template = ToscaTemplate(
            parsed_params=parsed_params, yaml_dict_tpl=yaml_dict
        )
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
    return template


def _get_dict(path):
    """
    Return the YAML dictionary
    """
    if os.path.isfile(path):
        with open(path, "r") as f:
            return yaml.safe_load(f)

    try:
        f = urllib.request.urlopen(path)
        return yaml.safe_load(f)
    except urllib.error.URLError as e:
        logger.error("the input file doesn't exist or cannot be reached")
        raise Exception("Cannot find input file {}".format(e))


def _determine_inputs(tpl_dict, parsed_params):
    """
    Store input values from parsed_params or defaults
    """
    params = parsed_params if parsed_params else {}
    inputs = tpl_dict.get("topology_template", {}).get("inputs", {})
    values = {}
    for key, value in inputs.items():
        values[key] = params.get(key) or value["default"]
    return values


def _resolve_occurrences(tpl_dict, parsed_params):
    """
    Handle TOSCA v1.3 occurrences feature, for now
    """
    nodes = tpl_dict.get("topology_template", {}).get("node_templates")
    inputs = _determine_inputs(tpl_dict, parsed_params)
    nodes_with_occurrences = [
        node for node in nodes if "occurrences" in nodes[node]
    ]
    print(nodes_with_occurrences)
    for node in nodes_with_occurrences:
        new_nodes = _create_occurrences(node, nodes.pop(node), inputs)
        nodes.update(new_nodes)


def _create_occurrences(name, node, inputs):
    """
    Create and return a dictionary of new occurrences
    """
    occurrences = node.pop("occurrences")
    count = node.pop("instance_count", occurrences[0])
    if isinstance(count, str):
        count = int(count)
    elif isinstance(count, dict):
        try:
            count = int(inputs[count["get_input"]])
        except (KeyError, TypeError):
            raise KeyError("Could not resolve instance_count")

    new_nodes = {}
    for i in range(count):
        new_name = f"{name}-{i+1}"
        new_node = copy.deepcopy(node)
        resolve_get_inputs(
            new_node,
            _set_indexed_input,
            lambda x: isinstance(x, list),
            inputs,
            i,
        )

        new_nodes[new_name] = new_node

    return new_nodes


def _set_indexed_input(result, inputs, index):
    """
    Set the value of indexed inputs
    """
    if result[1] != "INDEX":
        raise TypeError("Unrecognised get_input format")
    try:
        return inputs[result[0]][index]
    except IndexError:
        raise IndexError(
            f"Input '{result[0]}' does not match node occurrences!"
        ) from None


def _find_other_inputs(template):
    resolve_get_inputs(
        template.tpl, _get_input_value, lambda x: x is not None, template
    )
    # Update nodetemplate properties
    for node in template.nodetemplates:
        node._properties = node._create_properties()


def _get_input_value(key, template):
    try:
        return template.parsed_params[key]
    except (KeyError, TypeError):
        logger.debug(f"Input '{key}' not given, using default")

    try:
        return [
            param.default for param in template.inputs if param.name == key
        ][0]
    except IndexError:
        logger.error(f"Input '{key}' has no default")
