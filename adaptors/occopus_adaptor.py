import filecmp
import os
import logging
import docker
import ruamel.yaml as yaml
import time
import requests
import utils

import jinja2

from abstracts import base_adaptor as abco
from abstracts.exceptions import AdaptorCritical
from toscaparser.tosca_template import ToscaTemplate
from api import validate_only

logger = logging.getLogger("adaptor."+__name__)


class OccopusAdaptor(abco.Adaptor):

    def __init__(self, adaptor_id, config, dryrun, template=None):
        super().__init__()
        """
        Constructor method of the Adaptor
        """
        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")
        self.status = "init"
        self.dryrun = dryrun
        self.config = config
        self.node_prefix = "node_def:"
        self.node_name = ""
        self.worker_infra_name = "micado_worker_infra"
        self.min_instances = 1
        self.max_instances = 1
        self.ID = adaptor_id
        self.template = template
        self.node_path = "{}{}.yaml".format(self.config['volume'], self.ID)
        self.node_path_tmp = "{}tmp_{}.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_output = "{}{}-infra.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_output_tmp = "{}{}-infra.tmp.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_input = "./system/infrastructure_descriptor.yaml"
        self.cloudinit_path = "./system/cloud_init_worker.yaml"

        self.node_data = {}
        self.node_def = {}

        self.created = False
        self.client = None
        self.occopus = None
        if not self.dryrun:
                self._init_docker()

        self.occopus_address = "occopus:5000"
        self.auth_data_file = "/var/lib/micado/occopus/data/auth_data.yaml"
        self.occo_node_path = "/var/lib/micado/occopus/submitter/{}.yaml".format(self.ID)
        self.occo_infra_path = "/var/lib/micado/occopus/submitter/{}-infra.yaml".format(self.ID)
        logger.info("Occopus Adaptor initialised")

    def translate(self, tmp=False):
        """
        Translate the self.tpl subset to Occopus node definition and infrastructure format
        The adaptor create a mapping between TOSCA and Occopus template descriptor.
        """
        self.node_def = {}
        logger.info("Starting OccoTranslation")
        self.status = "translating"

        for node in self.template.nodetemplates:

            self.node_name = node.name.replace('_','-')
            self.node_data = {}

            cloud_type = self._node_data_get_interface(node, "resource")
            if not cloud_type:
                continue
            elif cloud_type == "cloudsigma":
                logger.info("CloudSigma resource detected")
                self._node_data_get_cloudsigma_host_properties(node, "resource")
            elif cloud_type == "ec2":
                logger.info("EC2 resource detected")
                self._node_data_get_ec2_host_properties(node, "resource")
            elif cloud_type == "cloudbroker":
                logger.info("CloudBroker resource detected")
                self._node_data_get_cloudbroker_host_properties(node, "resource")
            elif cloud_type == "nova":
                logger.info("Nova resource detected")
                self._node_data_get_nova_host_properties(node, "resource")

            self._get_policies()
            self._get_infra_def(tmp)

            node_type = self.node_prefix + self.node_name
            self.node_def.setdefault(node_type, [])
            self.node_def[node_type].append(self.node_data)

            if not validate_only:
                if tmp:
                    utils.dump_order_yaml(self.node_def, self.node_path_tmp)
                else:
                    utils.dump_order_yaml(self.node_def, self.node_path)

        self.status = "translated"

    def execute(self):
        """
        Import Occopus node definition, and build up the infrastructure
        through occopus container.
        """
        logger.info("Starting Occopus execution {}".format(self.ID))
        self.status = "executing"

        if self.dryrun:
                logger.info("DRY-RUN: Occopus execution in dry-run mode...")
                self.status = "DRY-RUN Deployment"
                return

        else:
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
                        exit_code, out = self.occopus.exec_run("occopus-build {} -i {} --auth_data_path {} --parallelize"
                                                        .format(self.occo_infra_path,
                                                                self.worker_infra_name,
                                                                self.auth_data_file))
                        if exit_code == 1:
                            raise AdaptorCritical(out)
                        occo_api_call = requests.post("http://{0}/infrastructures/{1}/attach"
                                                .format(self.occopus_address, self.worker_infra_name))
                        if occo_api_call.status_code != 200:
                            raise AdaptorCritical("Cannot submit infra to Occopus API!")
                        logger.info("Occopus build has been successful")
                        
                    except docker.errors.APIError as e:
                        logger.error("{0}. Error caught in calling Docker container".format(str(e)))
                    except requests.exceptions.RequestException as e:
                        logger.error("{0}. Error caught in call to occopus API".format(str(e)))
                else:
                    logger.error("Occopus import was unsuccessful!")
            else:
                logger.error("Occopus is not created!")
        self.status = "executed"
    def undeploy(self):
        """
        Undeploy Occopus infrastructure through Occopus rest API
        """
        self.status = "undeploying"
        logger.info("Undeploy {} infrastructure".format(self.ID))
        if self.dryrun:
                logger.info("DRY-RUN: deleting infrastructure...")
        else:
            requests.delete("http://{0}/infrastructures/{1}".format(self.occopus_address, self.worker_infra_name))
            # self.occopus.exec_run("occopus-destroy --auth_data_path {0} -i {1}"
            # .format(self.auth_data_file, self.worker_infra_name))
        self.status = "undeployed"

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
        Check that if it's any change in the node definition or in the cloud-init file.
        If the node definition changed then rerun the build process. If the node definition
        changed first undeploy the infrastructure and rebuild it with the modified parameter.
        """
        self.status = "updating"
        self.min_instances = 1
        self.max_instances = 1
        logger.info("Updating the component config {}".format(self.ID))
        self.translate(True)

        if not self._differentiate(self.node_path,self.node_path_tmp):
            logger.debug("Node tmp file different, replacing old config and executing")
            os.rename(self.node_path_tmp, self.node_path)
            os.rename(self.infra_def_path_output_tmp, self.infra_def_path_output)
            # Undeploy the infra and rebuild
            self.undeploy()
            self.execute()
            self.status = "updated"
            logger.debug("Node definition changed")
        elif not self._differentiate(self.infra_def_path_output, self.infra_def_path_output_tmp):
            logger.debug("Infra tmp file different, replacing old config and executing")
            os.rename(self.infra_def_path_output_tmp, self.infra_def_path_output)
            # Rerun Occopus build to refresh infra definition
            self.execute()
            self.status = "updated"
        else:
            self.status = 'updated (nothing to update)'
            logger.info("there are no changes in the Occopus files")
            try:
                logger.debug("Tmp file is the same, removing the tmp files")
                os.remove(self.node_path_tmp)
                os.remove(self.infra_def_path_output_tmp)
            except OSError as e:
                logger.warning(e)

    def _node_data_get_interface(self, node, key):
        """
        Get cloud relevant information from tosca
        """
        interfaces = node.interfaces
        try:
            occo_inf = [inf for inf in interfaces if inf.type == "Occopus"][0]
        except (IndexError, AttributeError):
            logger.debug("No interface for Occopus in {}".format(node.name))
        else:
            cloud_inputs = occo_inf.inputs
            self.node_data.setdefault(key, {}).setdefault("type", cloud_inputs["interface_cloud"])
            self.node_data.setdefault(key, {}).setdefault("endpoint", cloud_inputs["endpoint_cloud"])

            return cloud_inputs["interface_cloud"]
        return None


    def _node_data_get_context_section(self,properties):
        """
        Create the context section in node definition
        """
        self.node_data.setdefault("contextualisation", {}) \
            .setdefault("type", "cloudinit")

        if properties.get("context") is not None:
            context=properties.get("context").value
            if context.get("cloud_config") is None:
                if context["append"]:
                    # Missing cloud-config and append set to yes
                    logger.info("You set append properties but you do not have cloud_config. Please check it again!")
                    raise AdaptorCritical("You set append properties but you don't have cloud_config. Please check it again!")
                else:
                    # Append false and cloud-config is not exist - get default cloud-init
                    logger.info("Get default cloud-config")
                    self.node_data.setdefault("contextualisation", {}) \
                    .setdefault("context_template", self._get_cloud_init(context.get("cloud_config"),False,False))
            else:
                if context["append"]:
                    # Append Tosca context to the default config
                    logger.info("Append the TOSCA cloud-config with the default config")
                    self.node_data.setdefault("contextualisation", {}) \
                    .setdefault("context_template", self._get_cloud_init(context["cloud_config"],True,False))
                else:
                    # Use the TOSCA context
                    logger.info("The adaptor will use the TOSCA cloud-config")
                    self.node_data.setdefault("contextualisation", {}) \
                    .setdefault("context_template", self._get_cloud_init(context["cloud_config"],False,True))
        else:
            self.node_data.setdefault("contextualisation", {}) \
                    .setdefault("context_template", self._get_cloud_init(None,False,False))

    def _node_data_get_cloudsigma_host_properties(self, node, key):
        """
        Get CloudSigma properties and create node definition
        """
        properties = self._get_host_properties(node)
        nics = dict()

        self.node_data.setdefault(key, {})\
            .setdefault("libdrive_id", properties["libdrive_id"].value)
        self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("cpu", properties["num_cpus"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("mem", properties["mem_size"].value)
        self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("vnc_password", properties["vnc_password"].value)
        if properties.get("public_key_id") is not None:
            pubkeys = list()
            pubkeys.append(properties["public_key_id"].value)
            self.node_data[key]["description"]["pubkeys"] = pubkeys
        if properties.get("hv_relaxed") is not None:
            self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("hv_relaxed", properties["hv_relaxed"].value)
        if properties.get("hv_tsc") is not None:
            self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("hv_tsc", properties["hv_tsc"].value)
        nics=properties.get("nics").value
        self.node_data[key]["description"]["nics"] = nics
        self._node_data_get_context_section(properties)
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _node_data_get_ec2_host_properties(self, node, key):
        """
        Get EC2 properties and create node definition
        """
        properties = self._get_host_properties(node)

        self.node_data.setdefault(key, {}) \
            .setdefault("regionname", properties["region_name"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("image_id", properties["image_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("instance_type", properties["instance_type"].value)
        self._node_data_get_context_section(properties)
        if properties.get("key_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("key_name", properties["key_name"].value)
        if properties.get("subnet_id") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("subnet_id", properties["subnet_id"].value)
        if properties.get("security_group_ids") is not None:
            security_groups = list()
            security_groups = properties["security_group_ids"].value
            self.node_data[key]["security_group_ids"] = security_groups
        if properties.get("tags") is not None:
            tags = properties["tags"].value
            self.node_data[key]["tags"] = tags
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _node_data_get_cloudbroker_host_properties(self, node, key):
        """
        Get CloudBroker properties and create node definition
        """
        properties = self._get_host_properties(node)

        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("deployment_id", properties["deployment_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("instance_type_id", properties["instance_type_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("key_pair_id", properties["key_pair_id"].value)
        if properties.get("opened_port") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("description", {}) \
              .setdefault("opened_port", properties["opened_port"].value)
        self._node_data_get_context_section(properties)
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _node_data_get_nova_host_properties(self, node, key):
        """
        Get NOVA properties and create node definition
        """
        properties = self._get_host_properties(node)

        self.node_data.setdefault(key, {}) \
            .setdefault("project_id", properties["project_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("image_id", properties["image_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("network_id", properties["network_id"].value)
        self.node_data.setdefault(key, {}) \
            .setdefault("flavor_name", properties["flavor_name"].value)
        if properties.get("server_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("server_name", properties["server_name"].value)
        if properties.get("key_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("key_name", properties["key_name"].value)
        if properties.get("security_groups") is not None:
            self.node_data[key]["security_groups"] = properties["security_groups"].value
        self._node_data_get_context_section(properties)
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _get_cloud_init(self,tosca_cloud_config,append,override):
        """
        Get cloud-config from MiCADO cloud-init template
        """
        yaml.default_flow_style = False
        try:
            with open(self.cloudinit_path, 'r') as f:
                template = jinja2.Template(f.read())
                rendered = template.render(worker_name=self.node_name)
                default_cloud_config = yaml.round_trip_load(rendered, preserve_quotes=True)
        except OSError as e:
            logger.error(e)
        if override:
            return yaml.round_trip_load(tosca_cloud_config, preserve_quotes=True)
        if tosca_cloud_config is not None:
            tosca_cloud_config=yaml.round_trip_load(tosca_cloud_config, preserve_quotes=True)
        if append:
            for x in default_cloud_config:
                for y in tosca_cloud_config:
                    if x==y:
                        for z in tosca_cloud_config[y]:
                            default_cloud_config[x].append(z)
            return default_cloud_config
        else:
            return default_cloud_config

    def _get_infra_def(self, tmp):
        """Read infra definition and modify the min max instances according to the TOSCA policies.
        If the template doesn't have policy section or it is invalid then the adaptor set the default value """
        yaml.default_flow_style = False

        node_infra = {}
        node_infra['name'] = self.node_name
        node_infra['type'] = self.node_name
        node_infra.setdefault('scaling', {})['min'] = self.min_instances
        node_infra.setdefault('scaling', {})['max'] = self.max_instances

        if not tmp and os.path.isfile(self.infra_def_path_output):
            path = self.infra_def_path_output
        elif tmp and os.path.isfile(self.infra_def_path_output_tmp):
            path = self.infra_def_path_output_tmp
        else:
            path = self.infra_def_path_input

        try:
            with open(path, 'r') as f:
                infra_def = yaml.round_trip_load(f, preserve_quotes=True)
            infra_def.setdefault('nodes', [])
            infra_def["nodes"].append(node_infra)
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
                self.occopus = self.client.containers.list(filters={'label':'io.kubernetes.container.name=occopus'})[0]
                self.created = True
            except Exception as e:
                i += 1
                logger.error("{0}. Try {1} of 5.".format(str(e), i))
                time.sleep(5)

    def _get_host_properties(self, node):
        """ Get host properties """
        return node.get_properties()

    def _get_policies(self):
        """ Get the TOSCA policies """
        self.min_instances = 1
        self.max_instances = 1
        for policy in self.template.policies:
            for target in policy.targets_list:
                if self.node_name == target.name.replace('_', '-'):
                    logger.debug("policy target match for compute node")
                    properties = policy.get_properties()
                    self.min_instances = properties["min_instances"].value
                    self.max_instances = properties["max_instances"].value

    def _differentiate(self, path, tmp_path):
        """ Compare two files """
        return filecmp.cmp(path, tmp_path)
