from abstracts.exceptions import AdaptorError, AdaptorCritical


import logging

logger=logging.getLogger("submitter."+__name__)


class Step():
    def __init__(self, object):

        logger.info("intitialisation of Step, and execution of object's method ")
        self.object = object
        #super(Step, self).__init__()
    #def init_object(self):
    #    try:
    #        self.object()
    def translate(self):
        try:
            self.object.translate()
        except AdaptorCritical as e:
            logger.critical("critical error catched {}".format(e))
            raise
        except AdaptorError as e:
            logger.error("error catched {}, retry".format(e))
            raise


    def execute(self):
        try:
            self.object.execute()

        except AttributeError as e:
            logger.error("{}".format(e))
            raise
        except AdaptorCritical as e:
            logger.critical("{}".format(e))
            logger.info("nothing to be deployed")
            raise
    def update(self):
        try:
            self.object.update()
        except AdaptorCritical as e:
            logger.critical("critical error catched {}".format(e))
            raise

    def undeploy(self):
        try:
            self.object.undeploy()
        except Exception as e:
            logger.error(e)

    def cleanup(self):
        try:
            self.object.cleanup()
        except Exception as e:
            logger.error(e)
