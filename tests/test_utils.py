import unittest

from submitter.micado_parser import set_template
from submitter.adaptors.occopus_adaptor import OccopusAdaptor
from submitter.adaptors.terraform_adaptor import TerraformAdaptor


class TestOccopusUtils(unittest.TestCase):
    """Tests for OccopusAdaptor usage of utils"""

    def setUp(self):
        tpl = set_template("tests/templates/tosca.yaml", {})
        self.adaptor = OccopusAdaptor(
            "local_OccoAdaptor",
            {"volume": "tests/output/"},
            dryrun=True,
            validate=False,
            template=tpl,
        )

    def test_get_property_resolution_in_parent_tosca(self):
        node_def_dict = self.adaptor.translate(to_dict=True)
        endpoint = node_def_dict["node_def:cq-server"][0]["resource"][
            "endpoint"
        ]
        self.assertEqual(endpoint, "https://mycloud.net/api/v2")


class TestTerraUtils(unittest.TestCase):
    """Tests for TerraformAdaptor usage of utils"""

    def setUp(self):
        tpl = set_template("tests/templates/tosca.yaml", {})
        self.adaptor = TerraformAdaptor(
            "local_TerraAdaptor",
            {"volume": "tests/output/"},
            dryrun=True,
            validate=False,
            template=tpl,
        )

    def test_get_property_resolution_in_parent_tosca(self):
        json_dict = self.adaptor.translate(to_dict=True)
        endpoint = json_dict["provider"]["aws"]["endpoints"]["ec2"]
        self.assertEqual(endpoint, "https://mycloud.net/api/terra/v2")
