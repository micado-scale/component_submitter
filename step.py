import logging
from abstracts.exceptions import AdaptorError, AdaptorWarning, AdaptorCritical
logger=logging.getLogger("submitter."+__name__)


class Step():
    def __init__(self, object):
        logger.info("intitialisation of Step, and execution of object's execute method ")
        #super(Step, self).__init__()
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
