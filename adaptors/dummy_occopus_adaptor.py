
from abstracts import cloudorchestrator as abco
import logging
logger=logging.getLogger("adaptor."+__name__)


class DummyOccopusAdaptor(abco.CloudAdaptor):

    def __init__(self, adaptor_id, template = None):
        super().__init__()

        self.ID = adaptor_id
        self.template = template
        logger.info("OccoAdaptor initialised")

    def translate(self):

        logger.info("Starting Occotranslation")

    def execute(self):

        logger.info("Starting Occoexecution {}".format(self.ID))
    def undeploy(self):

        logger.info("undeploy {} infrastructure".format(self.ID))

    def cleanup(self):

        logger.info("cleaning up for infrastructure id {}".format(self.ID))

    def update(self):

        logger.info("updating the component config {}".format(self.ID))
