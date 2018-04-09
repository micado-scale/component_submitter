import logging

from abstracts import policykeeper as abco

logger=logging.getLogger("adaptor."+__name__)

class DummyPkAdaptor(abco.PolicyKeeperAdaptor):

    def __init__(self):
        super(DummyPkAdaptor, self).__init__()
        logger.info("PKAdaptor initialised")

    def translate(self, object):

        logger.info("Starting PKtranslation")

    def execute(self):

        logger.info("Starting PKexecution")

    def undeploy(self):

        logger.info("Undeploy/remove the policy in pk service")
