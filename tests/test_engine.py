import unittest

from submitter import submitter_engine


class TestEngine(unittest.TestCase):
    """UnitTests for submitter_engine"""

    def setUp(self):
        """Setup Validator object and prep a bad TOSCA template"""
        self.engine = submitter_engine.SubmitterEngine()

    def test_engine_init(self):
        """Test Engine init method"""
        self.assertIn("test_app", self.engine.app_list)