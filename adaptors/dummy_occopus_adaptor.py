import logging

from abstracts import cloudorchestrator as abco

logger=logging.getLogger("adaptor."+__name__)

class DummyOccopusAdaptor(abco.CloudAdaptor):

    def __init__(self):
        super(DummyOccopusAdaptor, self).__init__()
        logger.info("OccoAdaptor initialised")

    def translate(self, object):

        logger.info("Starting Occotranslation")

    def execute(self):

        logger.info("Starting Occoexecution")

    def undeploy(self):

        logger.info("undeploy infrastructure")
