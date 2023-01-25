import unittest

from submitter.submitter_engine import SubmitterEngine as SE


class TestEngine(unittest.TestCase):
    """UnitTests for submitter_engine"""

    def setUp(self):
        """Setup Validator object and prep a bad TOSCA template"""
        self.engine = SE()

    def test_engine_init(self):
        """Test Engine init method"""
        self.assertTrue(self.engine)