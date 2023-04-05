import unittest

from micadoparser.parser import set_template

from submitter.adaptors.occopus_adaptor import OccopusAdaptor


class TestOccopusAdaptor(unittest.TestCase):
    """UnitTests for Resource class"""

    def setUp(self) -> None:
        tpl = set_template("tests/templates/tosca.yaml")
        occoadaptor = OccopusAdaptor(
            "occo_test", {"volume": "tests/output/"}, True, template=tpl
        )
        translation = occoadaptor.translate(to_dict = True)
        self.worker = translation['node_def:worker-node'][0]


    def test_resource_keys(self):
    def test_health_check(self):
        healthcheck = {"ping": False}
        self.assertEqual(self.worker["health_check"], healthcheck)
