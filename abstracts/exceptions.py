class AdaptorError(Exception):
    """Base exception for adaptors"""

class NoRelevantData(AdaptorError):
    """When no data for the adaptor exists"""

class InvalidTosca(AdaptorError):
    """When the TOSCA template produces an error"""
