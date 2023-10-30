import unittest

from micadoparser.parser import set_template

from submitter.adaptors.ansible_adaptor.ansible_adaptor import AnsibleAdaptor


class TestAnsibleAdaptor(unittest.TestCase):
    """UnitTests for Ansible translate"""

    def setUp(self) -> None:
        tpl = set_template("tests/templates/edge.yaml")
        conf = {"volume": "tests/output/", "micado_host": "12.12.12.12"}
        ansiadaptor = AnsibleAdaptor(
            "edge_test", conf, True, template=tpl
        )
        self.nodes = ansiadaptor.translate(to_list=True)

    
    def test_edge_playbook(self):
        self.assertTrue(self.nodes)