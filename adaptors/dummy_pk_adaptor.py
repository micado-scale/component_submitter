import utils

from abstracts import policykeeper as abco
import logging
logger=logging.getLogger("adaptor."+__name__)

class DummyPkAdaptor(abco.PolicyKeeperAdaptor):

    def __init__(self, template = None, adaptor_id = None):

        super().__init__()
        if adaptor_id is None:
            self.ID = utils.id_generator()
        else:
            self.ID = adaptor_id
        self.templates = template
        logger.info("PKAdaptor initialised")

    def translate(self):

        logger.info("Starting PKtranslation")

    def execute(self):

        logger.info("Starting PKexecution")

    def undeploy(self):

        logger.info("Undeploy/remove the policy in pk service with id {}".format(self.ID))

    def cleanup(self):

        logger.info("cleaning up pk id {}".format(self.ID))

    def update(self, template):

        logger.info("updating the component config {}".format(self.ID))
