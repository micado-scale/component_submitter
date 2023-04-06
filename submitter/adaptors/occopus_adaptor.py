import filecmp
import os
import base64
import copy
import logging
import time

import jinja2
import requests
from toscaparser.tosca_template import ToscaTemplate

from submitter.abstracts import base_adaptor as abco
from submitter.abstracts.exceptions import AdaptorCritical
from submitter import utils

logger = logging.getLogger("adaptor."+__name__)

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
        self.auth_data_submitter = "/var/lib/micado/submitter/auth/auth_data.yaml"
        self.node_path = "{}{}.yaml".format(self.config['volume'], self.ID)
        self.node_path_tmp = "{}tmp_{}.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_output = "{}{}-infra.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_output_tmp = "{}{}-infra.tmp.yaml".format(self.config['volume'], self.ID)
        self.infra_def_path_input = "./system/infrastructure_descriptor.yaml"
        self.cloudinit_path = "./system/cloud_init_worker.yaml"

        self.node_data = {}
        self.node_def = {}

        self.created = False
        if not self.dryrun:
            utils.init_kubernetes()

        self.occopus_address = "occopus:5000"
        self.auth_data_file = "/var/lib/micado/occopus/auth/auth_data.yaml"
        self.occo_node_path = "/var/lib/micado/occopus/submitter/{}.yaml".format(self.ID)
        self.occo_infra_path = "/var/lib/micado/occopus/submitter/{}-infra.yaml".format(self.ID)
        logger.info("Occopus Adaptor initialised")

    def translate(self, tmp=False, to_dict=False):
        """
        Translate the self.tpl subset to Occopus node definition and infrastructure format
        The adaptor create a mapping between TOSCA and Occopus template descriptor.
        """
        CLOUD_TYPES = {
            "ec2": get_ec2_host_properties,
            "nova": get_nova_host_properties,
            "cloudsigma": get_cloudsigma_host_properties,
            "cloudbroker": get_cloudbroker_host_properties,
        }
        self.node_def = {}
        logger.info("Starting OccoTranslation")
        self.status = "translating"

        for node in self.template.nodetemplates:

            node = copy.deepcopy(node)
            occo_interface = utils.get_lifecycle(node, "Occopus")
            if not occo_interface:
                continue

            self.node_name = node.name
            self.node_data = {
                "resource": {},
                "contextualisation": {},
                "health_check": {
                  "ping": False
                },
            }

            # Start with whatever is in interfaces
            self.node_data.update(occo_interface.get("create", {}))
            fix_endpoint_in_interface(self.node_data)

            cloud_type = utils.get_cloud_type(node, CLOUD_TYPES.keys())
            properties = get_host_properties(node)

            if cloud_type in ["cloudsigma", "cloudbroker"]:
                description = self.node_data["resource"].get("description", {})
                description.update(properties)
                properties = description

            logger.info(f"Resource detected: {cloud_type}")
            try:
                CLOUD_TYPES[cloud_type](properties) # Call the right get function
            except KeyError:
                raise AdaptorCritical(f"Cloud type not supported: {cloud_type}")
            
            context = properties.pop("context", {})
            self.node_data["resource"].update(properties)

            self.node_data["contextualisation"] = self._node_data_get_context_section(context)
            
            self._get_policies(node)
            self._get_infra_def(tmp)

            node_type = self.node_prefix + self.node_name
            self.node_def.setdefault(node_type, [])
            self.node_def[node_type].append(self.node_data)

        if not self.node_def:
            self.status = "no occopus nodes found"
            return

        if to_dict:
            return self.node_def

        if tmp:
            utils.dump_order_yaml(self.node_def, self.node_path_tmp)
        elif self.validate is False:
            if not self.dryrun:
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

        logger.debug("Occopus import...")
        command = f"occopus-import {self.occo_node_path}"
        utils.exec_command_in_deployment(
            "occopus", command, success="Successfully imported nodes"
        )

        logger.debug("Occopus build...")
        command = "occopus-build {} -i {} --auth_data_path {} --parallelize".format(
            self.occo_infra_path, self.worker_infra_name, self.auth_data_file
        )
        utils.exec_command_in_deployment(
            "occopus", command, success="Submitted infrastructure"
        )

        logger.debug("Occopus attach...")
        occo_api_call = requests.post(
            "http://{0}/infrastructures/{1}/attach".format(
                self.occopus_address, self.worker_infra_name
            )
        )
        if occo_api_call.status_code != 200:
            raise AdaptorCritical("Cannot submit infra to Occopus API!")

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
            command = "redis-cli FLUSHALL"
            utils.exec_command_in_deployment("redis", command, success="OK")
        except AdaptorCritical:
            logger.warning("Could not connect to occo-redis container for FLUSH")
        except Exception:
            logger.warning("Unknown error trying to FLUSH occo-redis")

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


    def _node_data_get_context_section(self, context):
        """
        Create the context section in node definition
        """
        context_data = {
            "type": "cloudinit",
            "context_template": {}
        }
        base_cloud_init = context.get("path") or self.cloudinit_path
        cloud_config = context.get("cloud_config")
        if not context or not cloud_config:
            logger.debug("The adaptor will use a default cloud-config")
            context_data["context_template"] = self._get_cloud_init(None, base_cloud_init)
        else:
            mode = get_insert_mode(context)
            logger.debug(f"{mode.title()} the TOSCA cloud-config")
            context_data["context_template"] = self._get_cloud_init(cloud_config, base_cloud_init, mode)

        return context_data


    def _get_cloud_init(self,tosca_cloud_config, base_cloud_init, insert_mode=None):
        """
        Get cloud-config from MiCADO cloud-init template
        """
        default_cloud_config = {}
        try:
            with open(base_cloud_init, 'r') as f:
                template = jinja2.Template(f.read())
                rendered = template.render(worker_name=self.node_name)
                default_cloud_config = utils.get_yaml_data(rendered, stream=True)
        except OSError as e:
            logger.error(e)

        if not tosca_cloud_config:
            return default_cloud_config

        tosca_cloud_config = utils.get_yaml_data(
            tosca_cloud_config, stream=True
        )
        return utils.get_cloud_config(
            insert_mode, RUNCMD_PLACEHOLDER, default_cloud_config, tosca_cloud_config
        )

    def _get_infra_def(self, tmp):
        """Read infra definition and modify the min max instances according to the TOSCA policies.
        If the template doesn't have policy section or it is invalid then the adaptor set the default value """

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
                infra_def = utils.get_yaml_data(path)
                infra_def.setdefault('nodes', [])
                infra_def["nodes"].append(node_infra)
            except OSError as e:
                logger.error(e)

            if tmp:
                utils.dump_order_yaml(infra_def, self.infra_def_path_output_tmp)
            elif self.validate is False:
                utils.dump_order_yaml(infra_def, self.infra_def_path_output)



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
        secret_name = "cloud-credentials"
        
        auth_secret = utils.get_namespaced_secret(secret_name)
        auth_data = auth_secret.data
        auth_file = auth_data.get("auth_data.yaml", {})
        auth_file = base64.decodestring(auth_file.encode())
        auth_file = utils.get_yaml_data(auth_file, stream=True)

        # Modify the auth data
        for resource in auth_file.get("resource", []):
            if resource.get("type") == "nova":
                auth = resource.get("auth_data", {})
                self.modify_openstack_authentication(auth, changes)

        # Update the secret with the modified auth data
        if changes:
            new_auth_data = utils.dump_order_yaml(auth_file).encode()
            new_auth_data = base64.encodestring(new_auth_data)
            auth_data["auth_data.yaml"] = new_auth_data.decode()
            utils.patch_namespaced_secret(secret_name, auth_secret)
            self.wait_for_volume_update(changes)

    def wait_for_volume_update(self, changes):
        """ Wait for update changes to be reflected in the volume """
        wait_timer = 100
        logger.debug("Waiting for authentication data to update...")
        while wait_timer > 0:
            # Read the file in the submitter's auth volume
            try:
                auth_data = utils.get_yaml_data(self.auth_data_submitter)
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


def fix_endpoint_in_interface(node_data):
    """
    Adjust endpoint key in interface (legacy support for endpoint at root)

    This method will mutate interfaces to remove `endpoint` from top-level
    """
    # NOTE endpoint_cloud is deprecated
    # TODO deprecate endpoint at root and allow only under resource?
    endpoint = node_data.pop("endpoint", "")
    if not node_data.setdefault("resource", {}).setdefault("endpoint", endpoint):
        logger.error("Missing endpoint")
        raise AdaptorCritical("Missing endpoint")

def get_host_properties(node):
    """ Get host properties """
    return {x: y.value for x, y in node.get_properties().items()}

def get_ec2_host_properties(properties):
    """
    Get EC2 properties and create node definition
    """
    ec2 = properties
    ec2["type"] = "ec2"
    ec2["regionname"] = ec2.pop("region_name")
    return ec2

def get_nova_host_properties(properties):
    """
    Get Nova properties and create node definition
    """
    nova = properties
    nova["type"] = "nova"
    return nova

def get_cloudsigma_host_properties(properties):
    """
    Get CloudSigma properties and create node definition
    """
    cloudsigma = {}
    cloudsigma["type"] = "cloudsigma"

    cloudsigma["libdrive_id"] = properties.pop("libdrive_id")
    properties["cpu"] = properties.pop("num_cpus")
    properties["mem"] = properties.pop("mem_size")

    if (value := properties.pop("public_key_id", None)):
        properties["pubkeys"] = [value] # reformat as list

    cloudsigma["description"] = properties
    return cloudsigma

def get_cloudbroker_host_properties(properties):
    """
    Get CloudBroker properties and create node definition
    """
    cloudbroker = {}
    cloudbroker["type"] = "cloudbroker"

    domain_name_keys = (
        "dynamic_domain_name_id",
        "dynamic_domain_name",
    )
    for name in domain_name_keys:
        if not (value := properties.pop(name, None)):
            continue
        properties.setdefault(f"{name}s", {}).setdefault(name, value)

    cloudbroker["description"] = properties
    return cloudbroker

def get_insert_mode(context):
    modes = ("insert", "append", "overwrite")
    for mode in modes:
        if context.get(mode):
            return mode
    return "append"
