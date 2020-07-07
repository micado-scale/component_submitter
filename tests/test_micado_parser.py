import unittest

from toscaparser.tosca_template import ToscaTemplate

from micado_validator import MultiError
import micado_parser


class TestMiCADOParser(unittest.TestCase):
    """ UnitTests for micado_validator """

    def setUp(self):
        """ Setup Validator object and prep a bad TOSCA template """
        self.bad_tpl = ToscaTemplate("tests/templates/bad_tosca.yaml")
        self.good_tpl = ToscaTemplate("tests/templates/good_tosca.yaml")

    def test_bad_template(self):
        with self.assertRaises(MultiError):
            micado_parser.set_template("tests/templates/bad_tosca.yaml")

    def test_wrong_import(self):
        with self.assertRaises(Exception):
            micado_parser.set_template("tests/templates/wrong_import.yaml")

    def test_good_template(self):
        new_tpl = micado_parser.set_template("tests/templates/good_tosca.yaml")
        self.assertEqual(
            self.good_tpl.tpl,
            new_tpl.tpl,
        )
