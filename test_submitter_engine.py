import unittest
from submitter_engine import SubmitterEngine
import logging
logger=logging.getLogger("submitter."+__name__)


class SubmitterEngineTestCase(unittest.TestCase):
    def setUp(self):

        self.url_path = "https://raw.githubusercontent.com/COLAProject/COLARepo/dev/templates/inycom.yaml"
        self.url_path_j = "https://raw.githubusercontent.com/jaydesl/submission-adaptors/master/tosca.yaml"
        self.file_path = "./test/template/tpl.yaml"
        self.parsed_params = {"n":"d"}

    def test_input_url_path(self):
        logging.debug("\n\n\n")
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("test_input_url_path")
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        result = SubmitterEngine(path_to_file = self.url_path)
        logging.debug("\n\n\n")

    def test_input_url_path_j(self):
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("test_input_url_path_j")
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("{}".format(__name__))
        result = SubmitterEngine(path_to_file = self.url_path_j)
        logging.debug("\n\n\n")

    def test_input_file_path(self):
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("test_input_file_path")
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("{}".format(__name__))
        result = SubmitterEngine(path_to_file = self.file_path)
        logging.debug("\n\n\n")

    def test_parsed_params_file_path(self):
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("test_parsed_params_file_path")
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("{}".format(__name__))
        result = SubmitterEngine(path_to_file = self.url_path, parse_params = self.parsed_params)
        logging.debug("\n\n\n")


    def test_wrong_arg(self):
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("test_wrong_arg")
        logging.debug("--------------------------------------------------------------------------------------------------------------------------------------")
        logging.debug("{}".format(__name__))
        self.assertRaises(KeyError, SubmitterEngine, path_of_file = self.url_path)
        logging.debug("\n\n\n")

if __name__ == "__main__":
    unittest.main()
