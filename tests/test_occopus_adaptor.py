import unittest

from micadoparser.parser import set_template

from submitter.adaptors.occopus_adaptor import OccopusAdaptor
from submitter.adaptors import occopus_adaptor as occo

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
        self.assertListEqual(["endpoint", "type",'regionname', 'image_id', 'instance_type', 'key_name', 'security_group_ids'], list(self.worker["resource"].keys()))

    def test_health_check(self):
        healthcheck = {"ping": False}
        self.assertEqual(self.worker["health_check"], healthcheck)
        
    def test_endpoint_from_interface(self):
        endpoint = "ADD_YOUR_ENDPOINT (e.g https://ec2.eu-west-1.amazonaws.com)"
        test = {"create": {"endpoint": endpoint}}
        self.assertEqual(occo.get_endpoint_from_interface(test), endpoint)