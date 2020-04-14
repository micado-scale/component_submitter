import filecmp
import os
import base64
import copy
import logging
import docker
import ruamel.yaml as yaml
import time
import requests
import utils

import jinja2
import pykube

from abstracts import base_adaptor as abco
from abstracts.exceptions import AdaptorCritical
from toscaparser.tosca_template import ToscaTemplate

logger = logging.getLogger("adaptor."+__name__)

SUPPORTED_CLOUDS = (
    "ec2",
    "nova",
    "cloudsigma",
    "cloudbroker"
)
RUNCMD_PLACEHOLDER = "echo micado runcmd placeholder"

class OccopusAdaptor(abco.Adaptor):

    def __init__(self, adaptor_id, config, dryrun, validate=False, template=None):
        super().__init__()
        """
        Constructor method of the Adaptor
        """
        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")
        self.status = "init"
        self.dryrun = dryrun
        self.config = config
        self.validate = validate
        self.node_prefix = "node_def:"
        self.node_name = ""
        self.worker_infra_name = "micado_worker_infra"
        self.min_instances = 1
        self.max_instances = 1
        self.ID = adaptor_id
        self.template = template
        self.auth_data_submitter = "/var/lib/submitter/auth/auth_data.yaml"
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
        self.auth_data_file = "/var/lib/micado/occopus/auth/auth_data.yaml"
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

            if '_' in node.name:                
                raise AdaptorCritical("Underscores in node {} not allowed".format(node.name))
            self.node_name = node.name
            self.node_data = {}
            
            node = copy.deepcopy(node)
            occo_interface = self._node_data_get_interface(node)
            if not occo_interface:
                continue

            self._node_resolve_interface_data(node, occo_interface, "resource")
            cloud_type = utils.get_cloud_type(node, SUPPORTED_CLOUDS)

            if cloud_type == "cloudsigma":
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

            self._get_policies(node)
            self._get_infra_def(tmp)

            node_type = self.node_prefix + self.node_name
            self.node_def.setdefault(node_type, [])
            self.node_def[node_type].append(self.node_data)
        if self.node_def:
            if tmp:
                utils.dump_order_yaml(self.node_def, self.node_path_tmp)
            elif self.validate is False:
                self.prepare_auth_file()
                utils.dump_order_yaml(self.node_def, self.node_path)

        self.status = "translated"

    def execute(self):
        """
        Import Occopus node definition, and build up the infrastructure
        through occopus container.
        """
        logger.info("Starting Occopus execution {}".format(self.ID))
        self.status = "executing"
        if not self._config_files_exists():
            logger.info("No config generated during translation, nothing to execute")
            self.status = "Skipped"
            return
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
                        logger.debug("Occopus import starting...")
                        result = self.occopus.exec_run("occopus-import {0}".format(self.occo_node_path))
                        logger.debug("Occopus import has been successful")
                        run = True
                    except Exception as e:
                        i += 1
                        logger.debug("{0}. Try {1} of 5.".format(str(e), i))
                        time.sleep(5)
                logger.debug(result)
                if "Successfully imported" in result[1].decode("utf-8"):
                    try:
                        logger.debug("Occopus build starting...")
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
                        logger.debug("Occopus build has been successful")
                        
                    except docker.errors.APIError as e:
                        logger.error("{0}. Error caught in calling Docker container".format(str(e)))
                    except requests.exceptions.RequestException as e:
                        logger.error("{0}. Error caught in call to occopus API".format(str(e)))
                else:
                    logger.error("Occopus import was unsuccessful!")
                    raise AdaptorCritical("Occopus import was unsuccessful!")
            else:
                logger.error("Not connected to Occopus container!")
                raise AdaptorCritical("Occopus container connection was unsuccessful!")
        logger.info("Occopus executed")
        self.status = "executed"

    def undeploy(self):
        """
        Undeploy Occopus infrastructure through Occopus rest API
        """
        self.status = "undeploying"
        logger.info("Undeploy {} infrastructure".format(self.ID))
        if not self._config_files_exists():
            logger.info("No config generated during translation, nothing to undeploy")
            self.status = "Skipped"
            return
        elif self.dryrun:
            logger.info("DRY-RUN: deleting infrastructure...")
            self.status = "DRY-RUN Delete"
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
        if not self._config_files_exists():
            logger.info("No config generated during translation, nothing to cleanup")
            self.status = "Skipped"
            return
        try:
            os.remove(self.node_path)
            os.remove(self.infra_def_path_output)
        except OSError as e:
            logger.warning(e)
        # Flush the occopus-redis db
        try:
            redis = self.client.containers.list(filters={'label':'io.kubernetes.container.name=occopus-redis'})[0]
            if redis.exec_run("redis-cli FLUSHALL").exit_code != 0:
                raise AdaptorCritical
        except AdaptorCritical:
            logger.warning("FLUSH in occopus-redis container failed")
        except IndexError:
            logger.warning("Could not find occopus-redis container for FLUSH")
        except Exception:
            logger.warning("Could not connect to Docker for FLUSH")

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
        if not self.node_def and os.path.exists(self.node_path):
            logger.debug("No nodes in ADT, removing running nodes")
            self._remove_tmp_files()
            self.undeploy()
            self.cleanup()
            self.status = "Updated - removed all nodes"
        elif not self.node_def:
            logger.debug("No nodes found to be orchestrated with Occopus")
            self._remove_tmp_files()
            self.status = "Updated - no Occopus nodes"
        elif not os.path.exists(self.node_path):
            logger.debug("No running infrastructure, starting from new")
            os.rename(self.node_path_tmp, self.node_path)
            os.rename(self.infra_def_path_output_tmp, self.infra_def_path_output)
            self.execute()
            self.status = "updated"
        elif not self._differentiate(self.node_path,self.node_path_tmp):
            logger.debug("Node def file different, replacing old config and executing")
            os.rename(self.node_path_tmp, self.node_path)
            os.rename(self.infra_def_path_output_tmp, self.infra_def_path_output)
            # Detach from the infra and rebuild
            detach = requests.post("http://{0}/infrastructures/{1}/detach"
                                        .format(self.occopus_address, self.worker_infra_name))
            if detach.status_code != 200:
                raise AdaptorCritical("Cannot detach infra from Occopus API!")
            self.execute()
            self.status = "updated"
        elif not self._differentiate(self.infra_def_path_output, self.infra_def_path_output_tmp):
            logger.debug("Infra tmp file different, replacing old config and executing")
            os.rename(self.infra_def_path_output_tmp, self.infra_def_path_output)
            self._remove_tmp_files()
            # Rerun Occopus build to refresh infra definition
            self.execute()
            self.status = "updated"
        else:
            self.status = 'updated (nothing to update)'
            logger.info("there are no changes in the Occopus files")
            self._remove_tmp_files()

    def _node_data_get_interface(self, node):
        """
        Get interface for node from tosca
        """
        interfaces = utils.get_lifecycle(node, "Occopus")
        if not interfaces:
            logger.debug("No interface for Occopus in {}".format(node.name))
        return interfaces

    def _node_resolve_interface_data(self, node, interfaces, key):
        """
        Get cloud relevant information from tosca
        """
        cloud_inputs = utils.resolve_get_property(node, interfaces.get("create"))
        
        # DEPRECATE 'interface_cloud' to read cloud from TOSCA type
        #self.node_data.setdefault(key, {}).setdefault("type", cloud_inputs["interface_cloud"])

        # DEPRECATE 'endpoint_cloud' in favour of 'endpoint'
        endpoint = cloud_inputs.get("endpoint", cloud_inputs.get("endpoint_cloud"))
        self.node_data.setdefault(key, {}).setdefault("endpoint", endpoint)

    def _node_data_get_context_section(self, properties):
        """
        Create the context section in node definition
        """
        self.node_data.setdefault("contextualisation", {}).setdefault(
            "type", "cloudinit"
        )
        context = properties.get("context", {})
        cloud_config = context.get("cloud_config")
        if not context:
            logger.debug("The adaptor will use a default cloud-config")
            self.node_data["contextualisation"].setdefault(
                "context_template", self._get_cloud_init(None)
            )
        elif not cloud_config:
            logger.debug("No cloud-config provided... using default cloud-config")
            self.node_data["contextualisation"].setdefault(
                "context_template", self._get_cloud_init(None)
            )
        elif context.get("insert"):
            logger.debug("Insert the TOSCA cloud-config in the default config")
            self.node_data["contextualisation"].setdefault(
                "context_template", self._get_cloud_init(cloud_config, "insert")
            )
        elif context.get("append"):
            logger.debug("Append the TOSCA cloud-config to the default config")
            self.node_data["contextualisation"].setdefault(
                "context_template", self._get_cloud_init(cloud_config, "append")
            )
        else:
            logger.debug("Overwrite the default cloud-config")
            self.node_data["contextualisation"].setdefault(
                "context_template", self._get_cloud_init(cloud_config, "overwrite")
            )

    def _node_data_get_cloudsigma_host_properties(self, node, key):
        """
        Get CloudSigma properties and create node definition
        """
        properties = self._get_host_properties(node)
        nics = dict()
        self.node_data.setdefault(key, {}).setdefault("type", "cloudsigma")
        self.node_data.setdefault(key, {})\
            .setdefault("libdrive_id", properties["libdrive_id"])
        self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("cpu", properties["num_cpus"])
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("mem", properties["mem_size"])
        self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("vnc_password", properties["vnc_password"])
        if properties.get("public_key_id") is not None:
            pubkeys = list()
            pubkeys.append(properties["public_key_id"])
            self.node_data[key]["description"]["pubkeys"] = pubkeys
        if properties.get("hv_relaxed") is not None:
            self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("hv_relaxed", properties["hv_relaxed"])
        if properties.get("hv_tsc") is not None:
            self.node_data.setdefault(key, {})\
            .setdefault("description", {})\
            .setdefault("hv_tsc", properties["hv_tsc"])
        nics=properties.get("nics")
        self.node_data[key]["description"]["nics"] = nics
        self._node_data_get_context_section(properties)
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _node_data_get_ec2_host_properties(self, node, key):
        """
        Get EC2 properties and create node definition
        """
        properties = self._get_host_properties(node)

        self.node_data.setdefault(key, {}).setdefault("type", "ec2")
        self.node_data.setdefault(key, {}) \
            .setdefault("regionname", properties["region_name"])
        self.node_data.setdefault(key, {}) \
            .setdefault("image_id", properties["image_id"])
        self.node_data.setdefault(key, {}) \
            .setdefault("instance_type", properties["instance_type"])
        self._node_data_get_context_section(properties)
        if properties.get("key_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("key_name", properties["key_name"])
        if properties.get("subnet_id") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("subnet_id", properties["subnet_id"])
        if properties.get("security_group_ids") is not None:
            security_groups = list()
            security_groups = properties["security_group_ids"]
            self.node_data[key]["security_group_ids"] = security_groups
        if properties.get("tags") is not None:
            tags = properties["tags"]
            self.node_data[key]["tags"] = tags
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _node_data_get_cloudbroker_host_properties(self, node, key):
        """
        Get CloudBroker properties and create node definition
        """
        properties = self._get_host_properties(node)

        self.node_data.setdefault(key, {}).setdefault("type", "cloudbroker")
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("deployment_id", properties["deployment_id"])
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("instance_type_id", properties["instance_type_id"])
        self.node_data.setdefault(key, {}) \
            .setdefault("description", {}) \
            .setdefault("key_pair_id", properties["key_pair_id"])
        if properties.get("opened_port") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("description", {}) \
              .setdefault("opened_port", properties["opened_port"])
        if properties.get("infrastructure_component_id") is not None:
            self.node_data.setdefault(key,{}) \
              .setdefault("description", {}) \
              .setdefault("infrastructure_component_id", properties["infrastructure_component_id"])
        self._node_data_get_context_section(properties)
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _node_data_get_nova_host_properties(self, node, key):
        """
        Get NOVA properties and create node definition
        """
        properties = self._get_host_properties(node)
        
        self.node_data.setdefault(key, {}).setdefault("type", "nova")
        self.node_data.setdefault(key, {}) \
            .setdefault("project_id", properties["project_id"])
        self.node_data.setdefault(key, {}) \
            .setdefault("image_id", properties["image_id"])
        self.node_data.setdefault(key, {}) \
            .setdefault("network_id", properties["network_id"])
        self.node_data.setdefault(key, {}) \
            .setdefault("flavor_name", properties["flavor_name"])
        if properties.get("server_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("server_name", properties["server_name"])
        if properties.get("key_name") is not None:
            self.node_data.setdefault(key, {}) \
              .setdefault("key_name", properties["key_name"])
        if properties.get("security_groups") is not None:
            self.node_data[key]["security_groups"] = properties["security_groups"]
        self._node_data_get_context_section(properties)
        self.node_data.setdefault("health_check", {}) \
            .setdefault("ping",False)

    def _get_cloud_init(self,tosca_cloud_config,insert_mode=None):
        """
        Get cloud-config from MiCADO cloud-init template
        """
        yaml.default_flow_style = False
        default_cloud_config = {}
        try:
            with open(self.cloudinit_path, 'r') as f:
                template = jinja2.Template(f.read())
                rendered = template.render(worker_name=self.node_name)
                default_cloud_config = yaml.round_trip_load(rendered, preserve_quotes=True)
        except OSError as e:
            logger.error(e)

        if not tosca_cloud_config:
            return default_cloud_config

        tosca_cloud_config = yaml.round_trip_load(
            tosca_cloud_config, preserve_quotes=True
        )
        return utils.get_cloud_config(
            insert_mode, RUNCMD_PLACEHOLDER, default_cloud_config, tosca_cloud_config
        )

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
        if self.validate is False or tmp:
            try:
                infra_def = {}
                with open(path, 'r') as f:
                    infra_def = yaml.round_trip_load(f, preserve_quotes=True)
                infra_def.setdefault('nodes', [])
                infra_def["nodes"].append(node_infra)
            except OSError as e:
                logger.error(e)

            if tmp:
                with open(self.infra_def_path_output_tmp, 'w') as ofile:
                    yaml.round_trip_dump(infra_def, ofile)
            elif self.validate is False:
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
        return {x: y.value for x, y in node.get_properties().items()}

    def _get_policies(self, node):
        """ Get the TOSCA policies """
        self.min_instances = 1
        self.max_instances = 1
        if "scalable" in node.entity_tpl.get("capabilities", {}):
            scalable = node.get_capabilities()["scalable"]
            self.min_instances = scalable.get_property_value("min_instances")
            self.max_instances = scalable.get_property_value("max_instances")
            return
        for policy in self.template.policies:
            for target in policy.targets_list:
                if node.name == target.name:
                    logger.debug("policy target match for compute node")
                    properties = policy.get_properties()
                    self.min_instances = properties["min_instances"].value
                    self.max_instances = properties["max_instances"].value

    def prepare_auth_file(self):
        """ Prepare the Occopus auth file """
        # Pull the auth data out of the secret
        changes = {}
        try:
            auth_secret = self.load_auth_data_secret()
        except FileNotFoundError:
            logger.error("Auth data not found")
            raise AdaptorCritical
        auth_data = auth_secret.obj["data"]
        auth_file = auth_data.get("auth_data.yaml", {})
        auth_file = base64.decodestring(auth_file.encode())
        auth_file = yaml.safe_load(auth_file)

        # Modify the auth data
        for resource in auth_file.get("resource", []):
            if resource.get("type") == "nova":
                auth = resource.get("auth_data", {})
                self.modify_openstack_authentication(auth, changes)

        # Update the secret with the modified auth data
        if changes:
            new_auth_data = yaml.dump(auth_file).encode()
            new_auth_data = base64.encodestring(new_auth_data)
            auth_data["auth_data.yaml"] = new_auth_data.decode()
            auth_secret.update()
            self.wait_for_volume_update(changes)

    def load_auth_data_secret(self):
        """ Return the auth data secret """
        kube_config = pykube.KubeConfig.from_file("~/.kube/config")
        api = pykube.HTTPClient(kube_config)
        secrets = pykube.Secret.objects(api).filter(namespace="micado-system")
        for secret in secrets:
            if secret.name == "cloud-credentials":
                return secret
        raise FileNotFoundError
    
    def wait_for_volume_update(self, changes):
        """ Wait for update changes to be reflected in the volume """
        wait_timer = 100
        logger.debug("Waiting for authentication data to update...")
        while wait_timer > 0:
            # Read the file in the submitter's auth volume
            try:
                with open(self.auth_data_submitter) as auth_file:
                    auth_data = yaml.safe_load(auth_file)
            except FileNotFoundError:
                logger.error("Credential file missing...")
                raise AdaptorCritical

            # Check to see if the necessary changes have been reflected
            for cloud in auth_data.get("resource", []):
                cloud_type = cloud["type"]
                auth_type = cloud["auth_data"].get("type", "")
                if cloud_type in changes and auth_type == changes[cloud_type]:
                    return
            time.sleep(5)           
            wait_timer -= 5
        logger.warning("Got timeout while waiting for secret volume to update...")

    def modify_openstack_authentication(self, auth_data, changes):
        """ Modify the OpenStack credential type """
        if auth_data.get("type") == "application_credential":
            # Already up-to-date
            return

        app_cred_id = auth_data.pop("application_credential_id", None)
        app_cred_secret = auth_data.pop("application_credential_secret", None)
        if app_cred_id and app_cred_secret:
            auth_data["type"] = "application_credential"
            auth_data["id"] = app_cred_id
            auth_data["secret"] = app_cred_secret
            auth_data.pop("username", None)
            auth_data.pop("password", None)
            changes["nova"] = "application_credential"

    def _differentiate(self, path, tmp_path):
        """ Compare two files """
        return filecmp.cmp(path, tmp_path)

    def _config_files_exists(self):
        """ Check if config files were generated during translation """
        paths_exist = [os.path.exists(self.node_path), os.path.exists(self.infra_def_path_output)]
        return all(paths_exist)

    def _remove_tmp_files(self):
        """ Remove tmp files generated by the update step """
        try:
            os.remove(self.node_path_tmp)
            logger.debug("File deleted: {}".format(self.node_path_tmp))
        except OSError:
            pass
        try:
            os.remove(self.infra_def_path_output_tmp)
            logger.debug("File deleted: {}".format(self.infra_def_path_output_tmp))
        except OSError:
            pass
