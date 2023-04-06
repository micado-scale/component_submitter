import unittest

from micadoparser.parser import set_template

from submitter.adaptors.occopus_adaptor import OccopusAdaptor
from submitter.adaptors import occopus_adaptor as occo


class TestOccopusAdaptor(unittest.TestCase):
    """UnitTests for Occo translate"""

    def setUp(self) -> None:
        tpl = set_template("tests/templates/tosca.yaml")
        occoadaptor = OccopusAdaptor(
            "occo_test", {"volume": "tests/output/"}, True, template=tpl
        )
        translation = occoadaptor.translate(to_dict=True)
        self.worker = translation["node_def:worker-node"][0]
        self.cq = translation["node_def:cq-server"][0]

    def test_resource_keys(self):
        self.assertEqual(
            set(
                [
                    "endpoint",  # Added in properties...
                    "type",
                    "regionname",
                    "image_id",
                    "instance_type",
                    "key_name",
                    "security_group_ids",
                    "an_extra_prop",  # Added in interfaces
                ]
            ),
            set(self.worker["resource"].keys()),
        )

    def test_health_check(self):
        healthcheck = {"ping": False}
        self.assertEqual(self.worker["health_check"], healthcheck)

    def test_cloud_context(self):
        self.assertIn("context_template", self.worker["contextualisation"])

    def test_context_insert(self):
        runcmd = self.worker["contextualisation"]["context_template"]["runcmd"]
        self.assertTrue(runcmd[0].startswith("touch"))
        self.assertTrue(runcmd[1].startswith("wget"))
        self.assertTrue(runcmd[-1].startswith("banner"))

    def test_context_append(self):
        runcmd = self.cq["contextualisation"]["context_template"]["runcmd"]
        self.assertTrue(runcmd[0].startswith("touch"))
        self.assertTrue(runcmd[-1].startswith("wget"))


class TestOccoAdaptorFunctions(unittest.TestCase):
    """Unittests for Occo functions"""
    def test_endpoint_from_interface(self):
        endpoint = "https://ec2.eu-west-1.amazonaws.com"
        test = {"endpoint": endpoint}
        occo.fix_endpoint_in_interface(test)
        self.assertEqual(test["resource"]["endpoint"], endpoint)

    def test_cloudsigma_properties(self):
        test = {
            "libdrive_id": "123",
            "num_cpus": "2",
            "mem_size": "4G",
            "public_key_id": "abc",
        }
        node = occo.get_cloudsigma_host_properties(test)
        self.assertEqual(
            set(["description", "libdrive_id", "type"]),
            set(node.keys()),
        )
        self.assertEqual(
            set(["cpu", "mem", "pubkeys"]), set(node["description"].keys())
        )
        self.assertIsInstance(node["description"]["pubkeys"], list)

    def test_cloudbroker_properties(self):
        test = {"dynamic_domain_name": "web-frontend", "instance_type_id": "abc123"}
        node = occo.get_cloudbroker_host_properties(test)
        self.assertEqual(
            set(["description", "type"]),
            set(node.keys()),
        )
        self.assertEqual(test, node["description"])

    def test_ec2_properties(self):
        test = {"region_name": "eu-west-99"}
        node = occo.get_ec2_host_properties(test)
        self.assertIn("regionname", node)

    def test_nova_properties(self):
        test = {"flavor_name": "t2.small"}
        node = occo.get_nova_host_properties(test)
        self.assertEqual(node, test)

    def test_context_mode_getter(self):
        test = {"append": True, "cloud_config": {"runcmd": ["echo 'hi'"]}}
        mode = occo.get_insert_mode(test)
        self.assertEqual(mode, "append")

        test = {}
        mode = occo.get_insert_mode(test)
        self.assertEqual(mode, "overwrite")
