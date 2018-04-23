import logging
from abstracts.exceptions import AdaptorError, AdaptorCritical
logger=logging.getLogger("submitter."+__name__)


class Step():
    def __init__(self, object):
        logger.info("intitialisation of Step, and execution of object's execute method ")
        self.object = object
        #super(Step, self).__init__()
    #def init_object(self):
    #    try:
    #        self.object()
    def translate(self, params):
        try:
            return self.object.translate(params)
        except AdaptorCritical as e:
            logger.critical("critical error catched {}".format(e))
            raise
        except AdaptorError as e:
            logger.error("error catched {}, retry".format(e))
            raise


    def execute(self, id_element):
        try:
            self.object.execute(id_element)

        except AttributeError as e:
            logger.error("{}".format(e))
            raise
        except AdaptorCritical as e:
            logger.critical("{}".format(e))
            logger.info("nothing to be deployed")
            raise

    def undeploy(self, id):
        try:
            self.object.undeploy(id)
        except Exception as e:
            logger.error(e)
