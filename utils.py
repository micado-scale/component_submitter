import random
import string
import ruamel.yaml as yaml
import json
from six.moves import urllib
import codecs
import logging
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
    parent_interfaces = node.type_definition.interfaces.get(interface_type, {})
    for stage, value in parent_interfaces.items():
        if stage == "type":
            continue
        lifecycle[stage] = value.get("inputs")

    # Update these interfaces with any inputs from the current node
    interfaces = [x for x in node.interfaces if interface_type in x.type]
    for stage in interfaces:
        lifecycle.setdefault(stage.name, {}).update(stage.inputs or {})

    return lifecycle