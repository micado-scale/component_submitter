import logging
import utils

from abstracts import policykeeper as abco

logger=logging.getLogger("adaptor."+__name__)

class DummyPkAdaptor(abco.PolicyKeeperAdaptor):

    def __init__(self):
        super(DummyPkAdaptor, self).__init__()
        logger.info("PKAdaptor initialised")

    def translate(self, object):

        logger.info("Starting PKtranslation")
        return utils.id_generator()

    def execute(self, id_adaptor, outputs=None):

        logger.info("Starting PKexecution")

    def undeploy(self, id_adaptor):

        logger.info("Undeploy/remove the policy in pk service with id {}".format(id_adaptor))

    def cleanup(self, id_adaptor):

        logger.info("cleaning up pk id {}".format(id_adaptor))
