import unittest

from toscaparser.tosca_template import ToscaTemplate

from micado_validator import MultiError
from submitter_config import SubmitterConfig as SubConfig

class TestSubmitterConfig(unittest.TestCase):
    """ UnitTests for micado_validator """

    def setUp(self):
        """ Setup Validator object and prep a bad TOSCA template """
        self.config_path = "tests/configs/key_config.yaml"
        self.bad_tpl = ToscaTemplate("tests/templates/bad_tosca.yaml")
        self.good_tpl = ToscaTemplate("tests/templates/good_tosca.yaml")

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
    #def test_adaptor_config(self):
    #    dic = { "SecurityEnforcerAdaptor": { "types": ["tosca.policies.Scaling.*"], "endoint": "endpoint",  "volume": "/var/lib/submitter/security_workdir_example/", "dry_run": True}}
    #    self.assertDictEqual(dic, SubConfig(self.config_path).adaptor_config)

    #def test_adaptor_config(self):
    #    dic = {}
