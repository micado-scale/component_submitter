from toscaparser.tosca_template import ToscaTemplate
from adaptors.pk_adaptor import PkAdaptor
import ruamel.yaml as yaml


template = ToscaTemplate("tests/templates/stressng.yaml")

with open("system/key_config.yml") as stream:
    data = yaml.safe_load(stream)

adaptor = PkAdaptor("pk_test", data["PkAdaptor"], template)
adaptor.translate()
#adaptor.execute()