import logging
import generator

from abstracts import policykeeper as abco

logger=logging.getLogger("adaptor."+__name__)

class DummyPkAdaptor(abco.PolicyKeeperAdaptor):

    def __init__(self):
        super(DummyPkAdaptor, self).__init__()
        logger.info("PKAdaptor initialised")

    def translate(self, object):

        logger.info("Starting PKtranslation")
        return generator.id_generator()

    def execute(self, id_adaptor):

        logger.info("Starting PKexecution")

    def undeploy(self, id_adaptor):

        logger.info("Undeploy/remove the policy in pk service")
