import logging
logger=logging.getLogger("submitter."+__name__)


class Step():
    def __init__(self, object):
        logger.info("intitialisation of Step, and execution of object's execute method ")
        #super(Step, self).__init__()
        object.execute()
