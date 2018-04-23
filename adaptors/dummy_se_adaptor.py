import logging
import generator
from abstracts import securityenforcer as abco

logger=logging.getLogger("adaptor."+__name__)

class DummySeAdaptor(abco.SecurityEnforcerAdaptor):

    def __init__(self):
        super(DummySeAdaptor, self).__init__()
        logger.info("SeAdaptor initialised")

    def translate(self, object):

        logger.info("Starting Setranslation")
        return generator.id_generator()

    def execute(self, id_adaptor):

        logger.info("Starting Seexecution")

    def undeploy(self, id_adaptor):

        logger.info("Undeploy the Security in Security Enforcer")
