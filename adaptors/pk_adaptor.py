import os
import filecmp
import logging
import requests
from toscaparser.tosca_template import ToscaTemplate
<<<<<<< HEAD
from abstracts import base_adaptor as abco
=======
from abstracts import policykeeper as abco
>>>>>>> 8601ecd3cee3965393856c74caa502b5b304b3a8
from abstracts.exceptions import AdaptorCritical
import ruamel.yaml as yaml

logger = logging.getLogger("adaptor."+__name__)

# Hard-coded things for Pk
PK = (STACK, DATA, SOURCES, CONSTANTS, QUERIES, ALERTS, SCALING, NODES, SERVICES) = \
                ("stack", "data", "sources", "constants", "queries", "alerts", "scaling", "nodes", "services")


<<<<<<< HEAD
class PkAdaptor(abco.Adaptor):
=======
class PkAdaptor(abco.PolicyKeeperAdaptor):
>>>>>>> 8601ecd3cee3965393856c74caa502b5b304b3a8

    def __init__(self, adaptor_id, config, template=None):

        super().__init__()
        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")
        logger.info("Initialising the Pk adaptor with ID, config & TPL...")
        self.config = config
        self.pk_data = {}
        self.ID = adaptor_id
        try:
            self.path = "{}{}.yaml".format(self.config['volume'], self.ID)
            self.tmp_path = "{}tmp_{}.yaml".format(self.config['volume'], self.ID)
        except Exception as e:
            logger.error(e)
        self.tpl = template
        logger.info("Pk adaptor initialised")

    def translate(self, tmp=False):

        logger.info("Starting PK translation")
        # Hard-coded file structure
        self.pk_data = {STACK: self.ID.split("_")[0],
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
            logger.info("Policy of {0} is translated".format(target))

        if tmp is False:
            self._yaml_write(self.path)
            logger.info("PK file created")
        else:
            self._yaml_write(self.tmp_path)
            logger.info("Updated PK file created")

    def execute(self):
        logger.info("Starting Pk execution")
        headers = {'Content-Type': 'application/x-yaml'}
        try:
            with open(self.path, 'rb') as data:
                try:
                    requests.post("http://{0}/policy/start".format(self.config['endpoint']), data=data, headers=headers)
                except Exception as e:
                    logger.error(e)
                logger.info("Policy with {0} id is sent.".format(self.ID))
        except Exception as e:
            logger.error(e)


    def undeploy(self):
        logger.info("Removing the policy in Pk service with id {0}".format(self.ID))
        try:
            requests.post("http://{0}/policy/stop".format(self.config['endpoint']))
        except Exception as e:
            logger.error(e)
        logger.info("Policy {0} removed.".format(self.ID))


    def cleanup(self):

        logger.info("Cleanup config for ID {0}".format(self.ID))
        try:
            os.remove(self.path)
        except OSError as e:
            logger.warning(e)

    def update(self):
        logger.info("Updating the component config {0}".format(self.ID))
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
        try:
            with open(path, 'w') as ofile:
                yaml.round_trip_dump(self.pk_data, ofile, default_style='|', default_flow_style=False)
        except Exception as e:
            logger.error(e)

    def _differentiate(self):
        # Compare two Pk file
        return filecmp.cmp(self.path, self.tmp_path)
