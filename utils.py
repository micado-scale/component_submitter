import random
import string
import ruamel.yaml as yaml
from six.moves import urllib
import codecs
import logging
logger=logging.getLogger("submitter."+__name__)

class NoAliasRTDumper(yaml.RoundTripDumper):
    """ Turn off aliases, preserve order """
    def ignore_aliases(self, data):
        return True

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
