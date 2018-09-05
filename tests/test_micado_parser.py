import unittest

from toscaparser.tosca_template import ToscaTemplate

from micado_validator import MultiError
from  micado_parser import MiCADOParser

class TestMiCADOParser(unittest.TestCase):
    """ UnitTests for micado_validator """

    def setUp(self):
        """ Setup Validator object and prep a bad TOSCA template """
        self.bad_tpl = ToscaTemplate("tests/templates/bad_tosca.yaml")
        self.good_tpl = ToscaTemplate("tests/templates/good_tosca.yaml")
    def test_bad_template(self):
        with self.assertRaises(MultiError):
            MiCADOParser().set_template("tests/templates/bad_tosca.yaml")
    def test_wrong_import(self):
        with self.assertRaises(Exception):
            MiCADOParser().set_template("tests/templates/wrong_import.yaml")
    def test_good_template(self):
        self.good_tpl.__eq__(MiCADOParser().set_template("tests/templates/good_tosca.yaml"))
