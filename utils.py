import random
import string
import json
from six.moves import urllib
import codecs
import logging

import ruamel.yaml as yaml
from toscaparser.functions import GetProperty

logger=logging.getLogger("submitter."+__name__)

class NoAliasRTDumper(yaml.RoundTripDumper):
    """ Turn off aliases, preserve order """
    def ignore_aliases(self, data):
        return True

def load_json(path):
    """ Load the dictionary from a json file """    

    with open(path, 'r') as file:
        data = json.load(file)
        
    return data

def dump_json(data, path):
    """ Dump the dictionary to a json file """    

    with open(path, 'w') as file:
        json.dump(data, file, indent=4)

def dump_order_yaml(data, path):
    """ Dump the dictionary to a yaml file """    

    with open(path, 'w') as file:
        yaml.dump(data, file,
                  default_flow_style=False, Dumper=NoAliasRTDumper)

def dump_list_yaml(data, path):
    """ Dump a list of dictionaries to a single yaml file """    

    with open(path, 'w') as file:
        yaml.dump_all(data, file,
                  default_flow_style=False, Dumper=NoAliasRTDumper)

def get_yaml_data(path):
    """ Retrieve the yaml dictionary form a yaml file and return it """
    logger.debug("{}".format(path))
    try:
        f = urllib.request.urlopen(str(path))
    except ValueError as exc:
        logger.error("file is local: {}".format(exc))
        f = codecs.open(path, encoding='utf-8', errors='strict')
    return yaml.round_trip_load(f.read())


def id_generator(size=8, chars=string.ascii_uppercase + string.digits):
    """ Generate an ID """
    return ''.join(random.choice(chars) for _ in range(size))

def get_lifecycle(node, interface_type):
    """Get inputs from TOSCA interfaces

    First, gets the interface from the direct parent, then updates it with the
    TOSCA interface inputs from the current node

    Returns:
        dict: a set of inputs for different lifecycle stages
    """
    lifecycle = {}
    # Get the interfaces from the first parent
    try:
        parent_interfaces = node.type_definition.interfaces[interface_type]
    except (AttributeError, KeyError, TypeError):
        parent_interfaces = {}

    for stage, value in parent_interfaces.items():
        if stage == "type":
            continue
        try:
            lifecycle[stage] = value.get("inputs")
        except AttributeError:
            lifecycle[stage] = {}

    # Update these interfaces with any inputs from the current node
    interfaces = [x for x in node.interfaces if interface_type in x.type]
    for stage in interfaces:
        lifecycle.setdefault(stage.name, {}).update(stage.inputs or {})

    return lifecycle

def get_cloud_type(node, supported_clouds):
    """Get parent types of a node

    Returns the cloud type from node type or parent types

    Returns:
        string: lowercase node type
    """
    def generate_parents(node):
        while True:
            if not hasattr(node, "type"):
                break
            yield node.type.lower()
            node = node.parent_type
    
    for cloud in supported_clouds:
        if any(cloud in x for x in generate_parents(node)):
            return cloud

def resolve_get_property(node, cloud_inputs):
    """Resolve get property and return resolved inputs

    Returns:
        dict: resolved interface inputs
    """
    for field, value in cloud_inputs.items():
        if isinstance(value, GetProperty):
            cloud_inputs[field] = value.result()
            continue
        elif not isinstance(value, dict) or not "get_property" in value:
            continue
        cloud_inputs[field] = node.get_property_value(value.get("get_property")[-1])
    
    return cloud_inputs


def update_get_property(list_of_dict, properties):
    for field in list_of_dict:
        try:
            field.update(
                {
                    key: properties.get(value["get_property"][1])
                    for key, value in field.items()
                    if "get_property" in value
                }
            )
        except (TypeError, AttributeError):
            pass


def get_cloud_config(
    insert_mode, runcmd_placeholder, default_cloud_config, tosca_cloud_config
):

    if insert_mode == "overwrite":
        return tosca_cloud_config

    elif insert_mode == "insert":
        for x, y in tosca_cloud_config.items():
            try:
                idx = default_cloud_config[x].index(runcmd_placeholder)
                default_cloud_config[x][idx:idx] = y
            except (AttributeError, KeyError):
                default_cloud_config[x] = y
            except (ValueError, TypeError):
                default_cloud_config[x] = y + default_cloud_config[x]

    else:
        for x, y in tosca_cloud_config.items():
            try:
                if isinstance(default_cloud_config[x], bool):
                    default_cloud_config[x] = y
                else:
                    default_cloud_config[x] += y
            except KeyError:
                default_cloud_config[x] = y

    return default_cloud_config
