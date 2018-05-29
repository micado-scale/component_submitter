
from abstracts import policykeeper as abco
import logging
logger=logging.getLogger("adaptor."+__name__)

class DummyPkAdaptor(abco.PolicyKeeperAdaptor):

    def __init__(self, adaptor_id, config,  template = None):

        super().__init__()
        self.ID = adaptor_id
        self.templates = template
        self.config = config
        logger.info("PKAdaptor initialised")

    def translate(self):

        logger.info("Starting PKtranslation")

    def execute(self):

        logger.info("Starting PKexecution")

    def undeploy(self):

        logger.info("Undeploy/remove the policy in pk service with id {}".format(self.ID))

    def cleanup(self):

        logger.info("cleaning up pk id {}".format(self.ID))

    def update(self):

        logger.info("updating the component config {}".format(self.ID))
