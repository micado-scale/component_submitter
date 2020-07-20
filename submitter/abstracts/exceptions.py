class AdaptorError(Exception):
    """Base exception for adaptors"""

class AdaptorCritical(Exception):
    """When no data for the adaptor exists"""

class TranslateError(AdaptorCritical):
    """ For errors that occur during translation """

class ExecuteError(AdaptorCritical):
    """ For errors that occur during execution """
    
class UndeployError(AdaptorCritical):
    """ For errors that occur during tear down """