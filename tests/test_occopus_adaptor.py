import unittest

from micadoparser.parser import set_template

from submitter.adaptors.occopus_adaptor import OccopusAdaptor


class TestOccopusAdaptor(unittest.TestCase):
    """UnitTests for Resource class"""

    def setUp(self) -> None:
        tpl = set_template("tests/templates/tosca.yaml")
        occo = OccopusAdaptor(
            "occo_test", {"volume": "tests/output/"}, True, template=tpl
        )
        self.node_data = occo.translate(to_dict = True)

    def test_resource_keys(self):
        worker = self.node_data['node_def:worker-node'][0]['resource']
        self.assertListEqual(["endpoint", "type",'regionname', 'image_id', 'instance_type', 'key_name', 'security_group_ids'], list(worker.keys()))
