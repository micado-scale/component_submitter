import os
import filecmp
import logging
import requests
from toscaparser.tosca_template import ToscaTemplate
from abstracts import policykeeper as abco
from abstracts.exceptions import AdaptorCritical

import ruamel.yaml as yaml

logger = logging.getLogger("adaptor."+__name__)

# Hard-coded things for Pk
PK = (STACK, DATA, SOURCES, CONSTANTS, QUERIES, ALERTS, SCALING, NODES, SERVICES) = \
                ("stack", "data", "sources", "constants", "queries", "alerts", "scaling", "nodes", "services")


class PkAdaptor(abco.PolicyKeeperAdaptor):

    def __init__(self, adaptor_id, config, template=None):

        super().__init__()
        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")
        logger.debug("Initialising the PK adaptor with ID & TPL...")
        self.config = config
        self.pk_data = {}
        self.ID = adaptor_id
        # The path could be configured not hard-coded
        self.path = "{}{}.yaml".format(self.config['volume'], self.ID)
        self.tmp_path = "{}tmp_{}.yaml".format(self.config['volume'], self.ID)
        self.tpl = template
        logger.info("PKAdaptor initialised")

    def translate(self, tmp=False):

        logger.info("Starting PKtranslation")
        # Hard-coded file structure
        self.pk_data = {STACK: self.ID[:8],
                        SCALING: {}}

        i = 0
        node_name = None
        while i < len(self.tpl.nodetemplates) \
                and "tosca.nodes.MiCADO.Occopus" not in self.tpl.nodetemplates[i].type:
            i += 1
        if i < len(self.tpl.nodetemplates):
            node_name = self.tpl.nodetemplates[i].name

        for policy in self.tpl.policies:
            for target in policy.targets:
                if target == node_name:
                    self.pk_data[SCALING][NODES] = self._pk_scaling_properties(policy)
                else:
                    if self.pk_data[SCALING].get(SERVICES) is None:
                        self.pk_data[SCALING][SERVICES] = []
                    service = {"name": target}
                    service.update(self._pk_scaling_properties(policy))
                    self.pk_data[SCALING][SERVICES].append(service)

        if tmp is False:
            self._yaml_write(self.path)
        else:
            self._yaml_write(self.tmp_path)

    def execute(self):
        logger.info("Starting PKexecution")
        headers = {'Content-Type': 'application/x-yaml'}
        with open(self.path, 'rb') as data:
            requests.post("http://{0}/policy/start".format(self.config['endpoint']), data=data, headers=headers)


    def undeploy(self):
        logger.info("Undeploy/remove the policy in pk service with id {}".format(self.ID))
        # Hard-coded Pk address
        requests.post("http://{0}/policy/stop".format(self.config['endpoint']))


    def cleanup(self):

        logger.info("Cleanup config for ID {}".format(self.ID))
        try:
            os.remove(self.path)
        except OSError as e:
            logger.warning(e)

    def update(self):
        logger.info("updating the component config {}".format(self.ID))
        # If update
        logger.info("Starting the update...")
        logger.debug("Creating temporary template...")
        self.translate(True)

        if not self._differentiate():
            logger.debug("tmp file different, replacing old config and executing")
            os.rename(self.tmp_path, self.path)
            self.undeploy()
            self.execute()
        else:
            try:
                logger.debug("tmp file is the same, removing the tmp file")
                os.remove(self.tmp_path)
            except OSError as e:
                logger.warning(e)

    def _pk_scaling_properties(self, policy):
        policy_prop = {}
        properties = policy.get_properties()
        for prop in properties:
            if prop == SOURCES:
                self._pk_data_list(policy.get_property_value(prop), DATA, SOURCES)
            elif prop == CONSTANTS:
                self._pk_data_map(policy.get_property_value(prop), DATA, CONSTANTS)
            elif prop == QUERIES:
                self._pk_data_map(policy.get_property_value(prop), DATA, QUERIES)
            elif prop == ALERTS:
                self._pk_data_list(policy.get_property_value(prop), DATA, ALERTS)
            else:
                policy_prop[prop] = policy.get_property_value(prop)
        return policy_prop

    def _pk_data_list(self, list, key, nested_key):
        if self.pk_data.get(key) is None:
            self.pk_data[key] = {}
        if self.pk_data[key].get(nested_key) is None:
            self.pk_data[key][nested_key] = []
        for item in list:
            if self.pk_data[key][nested_key].count(item) == 0:
                self.pk_data[key][nested_key].append(item)

    def _pk_data_map(self, map, key, nested_key):
        if self.pk_data.get(key) is None:
            self.pk_data[key] = {}
        if self.pk_data[key].get(nested_key) is None:
            self.pk_data[key][nested_key] = {}
        for k, v in map.items():
            self.pk_data[key][nested_key][k] = v

    def _yaml_write(self, path):
        with open(path, 'w') as ofile:
            yaml.round_trip_dump(self.pk_data, ofile, default_style='|', default_flow_style=False)

    def _differentiate(self):
        # Compare two Pk file
        return filecmp.cmp(self.path, self.tmp_path)

