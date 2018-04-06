class AdaptorError(Exception):
    """Base exception for adaptors"""

class AdaptorCritical(Exception):
    """When no data for the adaptor exists"""

class AdaptorWarning(Exception):
    """When the TOSCA template produces an error"""
