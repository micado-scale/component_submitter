import unittest

from submitter.submitter_config import SubmitterConfig as SubConfig


class TestSubmitterConfig(unittest.TestCase):
    """UnitTests for micado_validator"""

    def setUp(self):
        """Setup Validator object and prep a bad TOSCA template"""
        config_path = "tests/configs/key_config.yaml"
        self.config = SubConfig(config_path)

    def test_main_config(self):
        self.assertTrue(self.config.main_config)
        self.assertTrue(self.config.step_config)
        self.assertTrue(self.config.logging_config)

    def test_get_adaptor_list(self):
        adaptors = [
            "SecurityEnforcerAdaptor",
            "DockerAdaptor",
            "PkAdaptor",
            "OccopusAdaptor",
        ]
        self.assertListEqual(sorted(self.config.get_list_adaptors()), sorted(adaptors))

    def test_step_config(self):
        dic = {
            "translate": [
                "SecurityEnforcerAdaptor",
                "DockerAdaptor",
                "OccopusAdaptor",
                "PkAdaptor",
            ],
            "execute": [
                "DockerAdaptor",
                "SecurityEnforcerAdaptor",
                "OccopusAdaptor",
                "PkAdaptor",
            ],
            "update": [
                "DockerAdaptor",
                "SecurityEnforcerAdaptor",
                "OccopusAdaptor",
                "PkAdaptor",
            ],
            "undeploy": [
                "SecurityEnforcerAdaptor",
                "DockerAdaptor",
                "OccopusAdaptor",
                "PkAdaptor",
            ],
            "cleanup": [
                "DockerAdaptor",
                "SecurityEnforcerAdaptor",
                "OccopusAdaptor",
                "PkAdaptor",
            ],
        }
        self.assertDictEqual(dic, self.config.step_config)
