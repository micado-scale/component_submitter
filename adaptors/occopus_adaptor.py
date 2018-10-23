import filecmp
import os
import logging
import docker
import ruamel.yaml as yaml
import time
import requests
import utils

from abstracts import base_adaptor as abco
from abstracts.exceptions import AdaptorCritical
from toscaparser.tosca_template import ToscaTemplate

logger = logging.getLogger("adaptor."+__name__)


class OccopusAdaptor(abco.Adaptor):

    def __init__(self, adaptor_id, config, status, template=None):
        super().__init__()
        """
        Constructor method of the Adaptor
        """
        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")
        self.status = status
        self.config = config
        self.node_name = "node_def:worker"
        self.worker_infra_name = "micado_worker_infra"
        self.min_instances = 1
        self.max_instances = 1
        self.ID = adaptor_id
        self.template = template
        self.node_path = "{}{}.yaml".format(self.config['volume'], self.ID)
        self.node_path_tmp = "{}tmp_{}.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_output = "{}{}-infra.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_output_tmp = "{}-infra.tmp.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_input = "/var/lib/submitter/system/infrastructure_descriptor.yaml"
        self.cloudinit_path = "/var/lib/submitter/system/cloud_init_worker.yaml"

        self.node_data = {}
        self.cloudsigma = {}
        self.ec2 = {}
        self.nova = {}
        self.cloudbroker = {}

        self.created = False
        self.client = None
        self.occopus = None
        self._init_docker()

        self.occopus_address = "occopus:5000"
        self.auth_data_file = "/var/lib/micado/occopus/data/auth_data.yaml"
        self.occo_node_path = "/var/lib/micado/occopus/submitter/{}.yaml".format(self.ID)
        self.occo_infra_path = "/var/lib/micado/occopus/submitter/{}-infra.yaml".format(self.ID)
        logger.info("Occopus Adaptor initialised")

    def translate(self, tmp=False):
        """
        Translate the self.tpl subset to Occopus node definition and infrastructure format
        Does the work of mapping the Occopus relevant sections of TOSCA into a
        dictionary, then dumping output to a .yaml files (infra and node def.) in output_configs/
        :param tmp: It is helping variable for update method. More information under update method
        :return:
        """
        self.node_data = {}
        logger.info("Starting OccoTranslation")
        ec2 = False
        nova = False
        cloudbroker = False
        cloudsigma = False

        for node in self.template.nodetemplates:
            if "tosca.nodes.MiCADO.Occopus.CloudSigma.Compute" in node.type:
                logger.info("CloudSigma resource detected")
                self._node_data_get_interface(node, "resource")
                self._node_data_get_cloudsigma_host_properties(node, "resource")
                self._get_policies()
                self._get_infra_def(tmp)
                cloudsigma = True
            if "tosca.nodes.MiCADO.Occopus.EC2.Compute" in node.type:
                logger.info("EC2 resource detected")
                self._node_data_get_interface(node, "resource")
                self._node_data_get_ec2_host_properties(node, "resource")
                self._get_policies()
                self._get_infra_def(tmp)
                ec2 = True
            if "tosca.nodes.MiCADO.Occopus.CloudBroker.Compute" in node.type:
                logger.info("CloudBroker resource detected")
                self._node_data_get_interface(node, "resource")
                self._node_data_get_cloudbroker_host_properties(node, "resource")
                self._get_policies()
                self._get_infra_def(tmp)
                cloudbroker = True
            if "tosca.nodes.MiCADO.Occopus.Nova.Compute" in node.type:
                logger.info("Nova resource detected")
                self._node_data_get_interface(node, "resource")
                self._node_data_get_nova_host_properties(node, "resource")
                self._get_policies()
                self._get_infra_def(tmp)
                nova = True

        if cloudsigma:
            self.cloudsigma = {self.node_name: []}
            self.cloudsigma[self.node_name].append(self.node_data)
            if tmp:
                utils.dump_order_yaml(self.cloudsigma, self.node_path_tmp)
            else:
                utils.dump_order_yaml(self.cloudsigma, self.node_path)
        elif ec2:
            self.ec2 = {self.node_name: []}
            self.ec2[self.node_name].append(self.node_data)
            if tmp:
                utils.dump_order_yaml(self.ec2, self.node_path_tmp)
            else:
                utils.dump_order_yaml(self.ec2, self.node_path)
        elif cloudbroker:
            self.cloudbroker = {self.node_name: []}
            self.cloudbroker[self.node_name].append(self.node_data)
            if tmp:
                utils.dump_order_yaml(self.cloudsigma, self.node_path_tmp)
            else:
                utils.dump_order_yaml(self.cloudbroker, self.node_path)
        elif nova:
            self.nova = {self.node_name: []}
            self.nova[self.node_name].append(self.node_data)
            if tmp:
                utils.dump_order_yaml(self.cloudsigma, self.node_path_tmp)
            else:
                utils.dump_order_yaml(self.nova, self.node_path)

    def execute(self):
        """
        Deploy Occopus infrastructure through Occopus rest API
        First the node definition should import in the Occopus
        contener and then the build process could go on REST API
        """
        logger.info("Starting Occopus execution {}".format(self.ID))
        if self.created:
            run = False
            i = 0
            while not run and i < 5:
                try:
                    logger.info("Occopus import starting...")
                    result = self.occopus.exec_run("occopus-import {0}".format(self.occo_node_path))
                    logger.info("Occopus import has been successful")
                    run = True
                except Exception as e:
                    i += 1
                    logger.error("{0}. Try {1} of 5.".format(str(e), i))
                    time.sleep(5)
            logger.info(result)
            if "Successfully imported" in result[1].decode("utf-8"):
                try:
                    logger.info("Occopus build starting...")
                    #headers = {'Content-Type': 'application/x-yaml'}
                    #with open(self.infra_def_path_output, 'rb') as data:
                    #    requests.post("http://{0}/infrastructures/"
                    # .format(self.occopus_address), data=data, headers=headers)
                    buildinfo = self.occopus.exec_run("occopus-build {} -i {} --auth_data_path {} --parallelize"
                                                      .format(self.occo_infra_path,
                                                              self.worker_infra_name,
                                                              self.auth_data_file))
                    logger.info(requests.post("http://{0}/infrastructures/{1}/attach"
                                              .format(self.occopus_address, self.worker_infra_name)))
                    logger.info("Occopus build has been successful")
                except Exception as e:
                    logger.error("{0}. Error caught in deploy phase".format(str(e)))
            else:
                logger.error("Occopus import was unsuccessful!")
        else:
            logger.error("Occopus is not created!")

    def undeploy(self):
        """
        Undeploy Occopus infrastructure through Occopus rest API
        """
        logger.info("Undeploy {} infrastructure".format(self.ID))
        requests.delete("http://{0}/infrastructures/{1}".format(self.occopus_address, self.worker_infra_name))
        # self.occopus.exec_run("occopus-destroy --auth_data_path {0} -i {1}"
        # .format(self.auth_data_file, self.worker_infra_name))

    def cleanup(self):
        """
        Remove the generated files under "files/output_configs/"
        """
        logger.info("Cleanup config for ID {}".format(self.ID))
        try:
            os.remove(self.node_path)
            os.remove(self.infra_def_path_output)
        except OSError as e:
            logger.warning(e)

    def update(self):
        """
        Check that if it's any change in the node definition or in the cloud init file.
        If the node definition changed then rerun the build process. If the node definition
        changed first undeploy the infrastructure and rebuild it with the modified parameter.
        """
        self.min_instances = 1
        self.max_instances = 1
        logger.info("Updating the component config {}".format(self.ID))
        self.translate(True)

        if not self._differentiate(self.node_path,self.node_path_tmp):
            logger.debug("Node tmp file different, replacing old config and executing")
            os.rename(self.node_path, self.node_path_tmp)
            os.rename(self.infra_def_path_output_tmp, self.infra_def_path_output)
            # Undeploy the infra and rebuild
            self.undeploy()
            self.execute()
            logger.debug("Node definition changed")
        elif not self._differentiate(self.infra_def_path_output, self.infra_def_path_output_tmp):
            logger.debug("Infra tmp file different, replacing old config and executing")
            os.rename(self.infra_def_path_output_tmp, self.infra_def_path_output)
            # Rerun Occopus build to refresh infra definition
            self.execute()
        else:
            logger.info("there are no changes in the Occopus files")
            try:
                logger.debug("Tmp file is the same, removing the tmp files")
                os.remove(self.node_path_tmp)
                os.remove(self.infra_def_path_output_tmp)
            except OSError as e:
                logger.warning(e)

    def _node_data_get_interface(self, node, key):
        """
        Get cloud relevant informations from tosca
        """
        properties = node.get_properties()
        entry = {}
        for prop in properties:
            try:
                entry[prop] = node.get_property_value(prop).result()
                node.get_property_value()
            except AttributeError as e:
                entry[prop] = node.get_property_value(prop)
        self.node_data.setdefault(key, {}).setdefault("type", entry["cloud"]["interface_cloud"])
        self.node_data.setdefault(key, {}).setdefault("endpoint", entry["cloud"]["endpoint_cloud"])

    def _node_data_get_context_section(self):
        """
        Create the context section in node definition
        """
        self.node_data.setdefault("contextualisation", {}) \
            .setdefault("type", "cloudinit")
        self.node_data.setdefault("contextualisation", {}) \
            .setdefault("context_template", self._get_cloud_init())

    def _node_data_get_cloudsigma_host_properties(self, node, key):
        """
        Get CloudSigma properties and create node definition
        """
        capabilites = self._get_host_properties(node)
        nics = list()
        dict = {}

        self.node_data.setdefault(key, {})\
            .setdefault("libdrive_id", capabilites["libdrive_id"].value)
        self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("cpu", capabilites["num_cpus"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("mem", capabilites["mem_size"].value)
        self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("vnc_password", capabilites["vnc_password"].value)
        if capabilites.get("public_key_id") is not None:
            pubkeys = list()
            pubkeys.append(capabilites["public_key_id"].value)
            self.node_data[key]["description"]["pubkeys"] = pubkeys
        if capabilites.get("firewall_policy") is not None:
            dict["firewall_policy"] = capabilites["firewall_policy"].value
        dict["ip_v4_conf"] = {}
        dict["ip_v4_conf"]["conf"] = "dhcp"
        nics.append(dict)
        self.node_data[key]["description"]["nics"] = nics
        self._node_data_get_context_section()

    def _node_data_get_ec2_host_properties(self, node, key):
        """
        Get EC2 properties and create node definition
        """
        capabilites = self._get_host_properties(node)

        self.node_data.setdefault(key, {}) \
            .setdefault("regionname", capabilites["region_name"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("image_id", capabilites["image_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("instance_type", capabilites["instance_type"].value)
        self._node_data_get_context_section()
        if capabilites.get("key_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("key_name", capabilites["key_name"].value)
        if capabilites.get("subnet_id") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("subnet_id", capabilites["subnet_id"].value)
        if capabilites.get("security_group_ids") is not None:
            security_groups = list()
            security_groups = capabilites["security_group_ids"].value
            self.node_data[key]["security_group_ids"] = security_groups

    def _node_data_get_cloudbroker_host_properties(self, node, key):
        """
        Get CloudBroker properties and create node definition
        """
        capabilites = self._get_host_properties(node)

        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("deployment_id", capabilites["deployment_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("instance_type_id", capabilites["instance_type_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("key_pair_id", capabilites["key_pair_id"].value)
        if capabilites.get("opened_port") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("description", {}) \
              .setdefault("opened_port", capabilites["opened_port"].value)
        self._node_data_get_context_section()
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _node_data_get_nova_host_properties(self, node, key):
        """
        Get NOVA properties and create node definition
        """
        capabilites = self._get_host_properties(node)

        self.node_data.setdefault(key, {}) \
            .setdefault("project_id", capabilites["project_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("image_id", capabilites["image_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("network_id", capabilites["network_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("flavor_name", capabilites["flavor_name"].value)
        if capabilites.get("server_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("server_name", capabilites["server_name"].value)
        if capabilites.get("key_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("key_name", capabilites["key_name"].value)
        if capabilites.get("security_groups") is not None:
            self.node_data[key]["security_groups"] = capabilites["security_groups"].value
        self._node_data_get_context_section()

    def _get_cloud_init(self):
        """
        Get cloud-config from MICADO-ansible template
        :return:
        """
        yaml.default_flow_style = False
        try:
            with open(self.cloudinit_path, 'r') as f:
                cloudinit = yaml.round_trip_load(f, preserve_quotes=True)
        except OSError as e:
            logger.error(e)

        return cloudinit

    def _get_infra_def(self, tmp):
        """Read infra def and modify the min max instances according to the Tosca policies.
        If the template doesn't have polcy section or it is invalid then set a default value """
        yaml.default_flow_style = False

        try:
            with open(self.infra_def_path_input, 'r') as f:
                infra_def = yaml.round_trip_load(f, preserve_quotes=True)
            infra_def["nodes"][0]["scaling"]["min"] = self.min_instances
            infra_def["nodes"][0]["scaling"]["max"] = self.max_instances
            infra_def["variables"]["master_host_ip"]
        except OSError as e:
            logger.error(e)

        if tmp:
            with open(self.infra_def_path_output_tmp, 'w') as ofile:
                yaml.round_trip_dump(infra_def, ofile)
        else:
            with open(self.infra_def_path_output, 'w') as ofile:
                yaml.round_trip_dump(infra_def, ofile)

    def _init_docker(self):
        """ Initialize docker and get Occopus container """
        self.client = docker.from_env()
        i = 0

        while not self.created and i < 5:
            try:
                self.occopus = self.client.containers.get('occopus')
                self.created = True
            except Exception as e:
                i += 1
                logger.error("{0}. Try {1} of 5.".format(str(e), i))
                time.sleep(5)

    def _get_host_properties(self, node):
        """ Get host properties """
        capabilites = node.get_capabilities()
        entry = capabilites.get("host")
        entry2 = entry.get_properties()
        return entry2

    def _get_policies(self):
        """ Get the TOSCA policies """
        target_name = ""
        i = 0
        found = False
        while i < len(self.template.nodetemplates) \
                and "tosca.nodes.MiCADO.Occopus" not in self.template.nodetemplates[i].type:
            i += 1
        if i < len(self.template.nodetemplates):
            target_name = self.template.nodetemplates[i].name
            found = True
        if found:
            for policy in self.template.policies:
                for target in policy.targets:
                    if target == target_name:
                        logger.debug("policy target found for Occopus")
                        properties = policy.get_properties()
                        self.min_instances = properties["min_instances"].value
                        self.max_instances = properties["max_instances"].value

    def _differentiate(self, path, tmp_path):
        """ Compare two files """
        return filecmp.cmp(path, tmp_path)
