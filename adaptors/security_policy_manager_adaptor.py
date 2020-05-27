"""
MiCADO Submitter Engine Security Policy Manager Adaptor
--------------------------------------------------

A TOSCA to Security Policy Manager adaptor.
"""

from toscaparser.tosca_template import ToscaTemplate

from abstracts import base_adaptor as abco
from abstracts.exceptions import AdaptorCritical
import logging
import requests
SECRET_TYPE = "tosca.policies.Security.MiCADO.Secret.KubernetesSecretDistribution"

logger = logging.getLogger("adaptors."+__name__)

class SecurityPolicyManagerAdaptor(abco.Adaptor):

    """ The Security Policy Manager adaptor class

    carries out the process of retreiving the security information of the
    TOSCA template described in the policy section, and pass it out to
    the Security Policy Manager.

    Implements abstract methods ``__init__()``, ``translate()``, ``execute()``,
    ``undeploy()`` and ``cleanup()``. Accepts as parameters an **adaptor_id**
    (required) and a **template** (optional). The ``translate()`` and ``update()``
    methods require both an **adaptor_id** and **template**. The ``execute()``,
    ``undeploy()`` and ``cleanup()`` methods require only the **adaptor_id** .

    :param string adaptor_id: The generated ID of the current application stack
    :param template: The ADT / ToscaTemplate of the current application stack
    :type template: ToscaTemplate <toscaparser.tosca_template.ToscaTemplate>

    Usage:
        >>> from security_policy_manager_adaptor import SecurityPolicyManagerAdaptor
        >>> se_adapt = SecurityPolicyManagerAdaptor(<adaptor_id>, <ToscaTemplate>)
        >>> se_adapt.translate()
            (does nothing but need to implement the abstract function anyways)
        >>> se_adapt.execute()
            (send the informations to the security policy manager)
        >>> se_adapt.update()
            (update the security policy manager with the new secret)
        >>> se_adapt.undeploy()
            (send the security policy manager a undeploy request)
        >>> se_adapt.cleanup()
            (does nothing as no files were created but need to implement the abstract function anyways)
    """

    def __init__(self, adaptor_id, config, dryrun, validate=False, template=None):
        """ Constructor method of the Adaptor as described above """
        super().__init__()
        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")
        self.tpl = template
        self.ID = adaptor_id
        self.config = config
        self.endpoint = 'http://10.97.170.199:5003/'
        'v1.0/nodecerts'
        self.status = "init"
        if template is not None:
            self.policies = self.tpl.policies
        logger.debug("Initialising the SE adaptor with the ID and TPL")

    def translate(self):
        pass

    def execute(self):
        self.status = "executing"
        """ Send to the Security Enforcer the informations
            retrieved from the TOSCA template"""
        for policy in self.policies:
            if SECRET_TYPE in policy.type:
                _interm_dict = policy.get_properties()["text_secrets"].value
                for key, value in _interm_dict.items():
                    if self.config["dry_run"] is True:
                        logger.info("launch api command with params name={} and value={} to {}/v1.0/appsecrets".format(key,value,self.endpoint))
                    elif self.config["dry_run"] is False:
                        data_keys = {'name':key, 'value':value}
                        logger.info("launch secret")
                        response = requests.post("{}/v1.0/appsecrets".format(self.endpoint), data = data_keys)
        self.status = "executed"

    def undeploy(self):
        """ Send to the Security Enforcer the id of the policy to undeploy """
        for policy in self.policies:
            if SECRET_TYPE in policy.type:
                _interm_dict = policy.get_properties()["text_secrets"].value
                for key, value in _interm_dict.items():
                    if self.config["dry_run"] is True:
                        logger.info("launch api command to delete secrets with {}/v1.0/appsecrets/{}".format(self.endpoint, key))
                    elif self.config["dry_run"] is False:
                        logger.info("launch secret delete")
                        response = requests.delete("{}/v1.0/appsecrets/{}".format(self.endpoint, key))
        self.status = "undeployed"


    def cleanup(self):
        pass

    def update(self):
        """ Send to the Security Enforcer if needed the updated policy """
        self.undeploy()
        self.execute()
