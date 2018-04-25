import logging
import generator

from abstracts import cloudorchestrator as abco

logger=logging.getLogger("adaptor."+__name__)

class DummyOccopusAdaptor(abco.CloudAdaptor):

    def __init__(self):
        super(DummyOccopusAdaptor, self).__init__()
        logger.info("OccoAdaptor initialised")

    def translate(self, object):

        logger.info("Starting Occotranslation")
        return generator.id_generator()

    def execute(self, id_adaptor, outputs=None):

        logger.info("Starting Occoexecution {}".format(id_adaptor))
    def undeploy(self, id_adaptor):

        logger.info("undeploy {} infrastructure".format(id_adaptor))

    def cleanup(self, id_adaptor):

        logger.info("cleaning up for infrastructure id {}".format(id_adaptor))
