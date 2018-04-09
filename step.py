import logging
from abstracts.exceptions import AdaptorError, AdaptorWarning, AdaptorCritical
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
            self.object.translate(params)
        except(AdaptorError, AdaptorCritical, AdaptorWarning) as e:
            if e is AdaptorCritical:
                logger.critical("critical error catched {}".format(e))
                raise
            if e is AdaptorError:
                logger.error("error catched {}, retry".format(e))
                raise
            if e is AdaptorWarning:
                logger.warning("warning: {}, keep going with process".format(e))


    def execute(self):
        try:
            object.execute()
        except (AttributeError, AdaptorError, AdaptorCritical, AdaptorWarning) as e:
            if e is AttributeError:
                logger.error("{}".format(e))
                raise
            if  e is AdaptorCritical:
                logger.critical("{}".format(e.message))
                logger.message("nothing to be deployed")
                raise

    def undeploy(self):
        try:
            object.undeploy()
        except Exception as e:
            logger.error(e)
