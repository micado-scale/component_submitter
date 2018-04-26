import random
import string
import ruamel.yaml as yaml
import logging
from six.moves import urllib
import codecs


logger =  logging.getLogger("submitter."+__name__)


def dump_order_yaml(data, path):
    """ Dump the dictionary to a Docker-Compose file """

    class NoAliasRTDumper(yaml.RoundTripDumper):
        """ Turn off aliases, preserve order """
        def ignore_aliases(self, data):
            return True

    with open(path, 'w') as file:
        yaml.dump(data, file,
                  default_flow_style=False, Dumper=NoAliasRTDumper)

def get_yaml_data(path):
    """ Retrieve the yaml dictionary form a yaml file and return it """
    logger.debug("{}".format(path))
    try:
        f = urllib.request.urlopen(str(path))
    except ValueError as exc:
        logger.error("file is local: {}".format(exc))
        f = codecs.open(path, encoding='utf-8', errors='strict')
    return yaml.load(f.read())


def id_generator(size=8, chars=string.ascii_uppercase + string.digits):
    """ Generate an ID """
    return ''.join(random.choice(chars) for _ in range(size))
