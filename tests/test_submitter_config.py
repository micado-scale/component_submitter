import unittest

from submitter.submitter_config import SubmitterConfig as SubConfig

class TestSubmitterConfig(unittest.TestCase):
    """ UnitTests for micado_validator """

    def setUp(self):
        """ Setup Validator object and prep a bad TOSCA template """
        self.config_path = "tests/configs/key_config.yaml"

    def test_main_config(self):
        s = SubConfig(self.config_path)
        self.assertTrue(s.main_config)
        self.assertTrue(s.step_config)
        self.assertTrue(s.logging_config)
    def test_step_config(self):
        dic = {"translate": ["SecurityEnforcerAdaptor", "DockerAdaptor", "OccopusAdaptor", "PkAdaptor"],
               "execute": ["DockerAdaptor", "SecurityEnforcerAdaptor", "OccopusAdaptor", "PkAdaptor"],
               "update": ["DockerAdaptor", "SecurityEnforcerAdaptor", "OccopusAdaptor", "PkAdaptor"],
               "undeploy": ["SecurityEnforcerAdaptor", "DockerAdaptor", "OccopusAdaptor", "PkAdaptor"],
               "cleanup": ["DockerAdaptor", "SecurityEnforcerAdaptor", "OccopusAdaptor", "PkAdaptor"]}
        self.assertDictEqual(dic, SubConfig(self.config_path).step_config)
