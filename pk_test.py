from toscaparser.tosca_template import ToscaTemplate
from adaptors.pk_adaptor import PkAdaptor
from adaptors.docker_adaptor import DockerAdaptor

template = ToscaTemplate("tests/templates/TOSCA-FILE2.yaml")

adaptor = PkAdaptor("pk_test", template)

adaptor.translate()