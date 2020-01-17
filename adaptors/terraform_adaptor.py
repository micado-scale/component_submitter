import filecmp
import os
import copy
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
from toscaparser.functions import GetProperty

logger = logging.getLogger("adaptor."+__name__)


class TerraformAdaptor(abco.Adaptor):

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
        self.node_name = ""
        self.min_instances = 1
        self.max_instances = 1
        self.ID = adaptor_id
        self.template = template
        self.start = True

        self.infra_def_path_input = "./system/infrastructure_descriptor.yaml"
        self.cloudinit_path = "./system/cloud_init_worker_tf.yaml"

        self.terra_final = "{}{}.tf".format(self.config['volume'],self.ID)
        self.terra_final_tmp = "{}{}.tf.tmp".format(self.config['volume'],self.ID)
        self.temp_terra_init = "{}terrainit.yaml".format(self.config['volume'])
        self.temp_terra_init_tmp = "{}terrainittmp.yaml".format(self.config['volume'])
        self.terra_var = "{}terraform.tfvars".format(self.config['volume'])
        self.terra_acc = "{}accounts.json".format(self.config['volume'])
        self.terra_var_tmp = "{}terraform.tfvars.tmp".format(self.config['volume'])

        self.tera_data = {}

        self.created = False
        self.client = None
        self.terraform = None
        if not self.dryrun:
                self._init_docker()

        self.terraform_address = "terraform:5000"
        self.auth_data_file = "/var/lib/submitter/system/auth_data.yaml"
        self.auth_gce = "/var/lib/submitter/system/accounts.json"
        self.master_cert = "/var/lib/submitter/system/master.pem"
        self.terra_azure_lin = "/var/lib/submitter/system/azure_lvm.tf"
        self.terra_azure_win = "/var/lib/submitter/system/azure_wvm.tf" 
        self.terra_gce = "/var/lib/submitter/system/gce_lvm.tf"
        self.terra_infra = "/var/lib/micado/terraform/submitter/{}.tf".format(self.ID)
        self.terra_init = "/var/lib/micado/terraform/submitter/terrainit.yaml"
        self.terra_path = "/var/lib/micado/terraform/submitter/"
        logger.info("Terraform adaptor initialised")

    def translate(self, tmp=False):
        """
        Translate the self.tpl subset to Terraform node infrastructure format
        This fuction creates a mapping between TOSCA and Terraform template descriptor.
        """
        logger.info("Starting Terraform Translation")
        self.status = "translating..."

        for node in self.template.nodetemplates:

            if '_' in node.name:
                raise AdaptorCritical("Underscores in node {} not allowed".format(node.name))
            self.node_name = node.name
            self.tera_data = {}

            node = copy.deepcopy(node)
            cloud_type = self._node_data_get_interface(node, "resource")
            if not cloud_type:
                continue
            elif cloud_type == "ec2":
                logger.info("EC2 resource detected")
                self._node_data_get_ec2_host_properties(node, "resource")
                self.tera_data.setdefault("type", "aws")
            elif cloud_type == "nova":
                logger.info("Nova resource detected")
                self._node_data_get_nova_host_properties(node, "resource")
                self.tera_data.setdefault("type", "nova")
            elif cloud_type == "azure":
                logger.info("Azure resource detected")
                self._node_data_get_azure_host_properties(node, "resource")
                self.tera_data.setdefault("type", "azure")
            elif cloud_type == "gce":
                logger.info("GCE resource detected")
                self._node_data_get_gce_host_properties(node, "resource")
                self.tera_data.setdefault("type", "gce")

            self._get_policies(node)
            self.tera_data.setdefault("name", self.node_name)

        if self.tera_data:
            if tmp:
                logger.info("Creating temp files")
                if cloud_type == "ec2":
                    self._write_tera_aws()
                elif cloud_type == "nova":
                    self._write_tera_nova()
                elif cloud_type == "azure":
                    self._write_tera_azure()
                elif cloud_type == "gce":
                    self._write_tera_gce()
            elif not self.validate:
                if cloud_type == "ec2":
                    self._write_tera_aws()
                elif cloud_type == "nova":
                    self._write_tera_nova()
                elif cloud_type == "azure":
                    self._write_tera_azure()
                elif cloud_type == "gce":
                    self._write_tera_gce()
                logger.info("First run")
                os.rename(self.terra_final_tmp,self.terra_final)
                os.rename(self.temp_terra_init_tmp,self.temp_terra_init)
                if cloud_type == "azure":
                    os.rename(self.terra_var_tmp,self.terra_var)
                if cloud_type == "gce":
                    os.rename(self.terra_var_tmp,self.terra_var)

        self.status = "Translated"

    def execute(self):
        """
        Initialize terraform execution environment and execute
        """
        logger.info("Starting Terraform execution {}".format(self.ID))
        self.status = "executing"
        if not self._config_file_exists():
            logger.info("No config generated during translation, nothing to execute")
            self.status = "Skipped"
            return
        elif self.dryrun:
            logger.info("DRY-RUN: Terraform execution in dry-run mode...")
            self.status = "DRY-RUN Deployment"
            return
        else:
            if self.created:

                if self.start:
                    logger.debug("Terraform initialization starting...")
                    result = self.terraform.exec_run("terraform init", workdir='{}'.format(self.terra_path))
                    logger.debug("Terraform initialization has been successful")
                    logger.debug(result)
                    self.start = False

                logger.debug("Terraform build starting...")
                exit_code, out = self.terraform.exec_run("terraform apply -var 'x={0}' -auto-approve".format(self.min_instances), workdir='{}'.format(self.terra_path))
                
 #               exit_code, out = self.terraform.exec_run("terraform apply -var 'x={0}' -auto-approve {1}".format(self.min_instances, self.terra_path))

                if exit_code == 1:
                    raise AdaptorCritical(out)
                logger.debug("Terraform build has been successful")

            else:
                logger.error("Terraform deployment was unsuccessfull!")
                raise AdaptorCritical("Terraform deployment was unsuccessful!")
        logger.info("Terraform executed")
        self.status = "executed"

    def undeploy(self):
        """
        Undeploy Terraform infrastructure
        """
        self.status = "undeploying"
        logger.info("Undeploying {} infrastructure".format(self.ID))
        if not self._config_file_exists():
            logger.info("No config generated during translation, nothing to undeploy")
            self.status = "Skipped"
            return
        elif self.dryrun:
            logger.info("DRY-RUN: deleting infrastructure...")
        else:

            self.terraform.exec_run("terraform destroy -lock=false -auto-approve", workdir='{}'.format(self.terra_path))
        self.status = "undeployed"

    def destroy_selected(self, vm_name):
        """
        Destroy a specific virtual machine
        """
        self.status = "updating"
        logger.info("Updating the infrastructure {}".format(self.ID))
        self.terraform.exec_run("terraform destroy -target={0} -lock=false -auto-approve", workdir='{}'.format(self.terra_path))

    def cleanup(self):
        """
        Remove the generated files under "files/output_configs/"
        """
        logger.info("Cleanup config for ID {}".format(self.ID))
        if not self._config_file_exists():
            logger.info("No config generated during translation, nothing to cleanup")
            self.status = "Skipped"
            return
        try:
            os.remove(self.terra_final)
            os.remove(self.temp_terra_init)
            if self.tera_data['type'] == "azure":
                os.remove(self.terra_var)
            if self.tera_data['type'] == "gce":
                os.remove(self.terra_var)
                os.remove(self.terra_acc)

        except OSError as e:
            logger.warning(e)

    def update(self):
        """
        Check that if it's any change in the node definition or in the cloud-init file.
        If the node definition changed then rerun the build process. If the infrastructure definition
        changed first undeploy the infrastructure and rebuild it with the modified parameter.
        """
        self.status = "updating"
        self.min_instances = 1
        self.max_instances = 1
        logger.info("Updating the infrastructure {}".format(self.ID))
        self.translate(True)
        if not self.tera_data and os.path.exists(self.terra_final):
            logger.debug("No nodes in ADT, removing running nodes")
            self._remove_tmp_files
            self.undeploy()
            self.cleanup()
            self.status = "Updated - removed all nodes"
        elif not self.tera_data:
            logger.debug("No nodes found to be orchestrated with Terraform")
            self._remove_tmp_files
            self.status = "Skipped"
        elif not self._differentiate(self.terra_final,self.terra_final_tmp):
            logger.debug("Infrastructure file changed, replacing old config and executing")
            os.rename(self.terra_final_tmp,self.terra_final)
            os.rename(self.temp_terra_init_tmp,self.temp_terra_init)
            self.execute()
            self.status = "Updated"
            logger.debug("Infrastructure changed")
        elif not self._differentiate(self.temp_terra_init,self.temp_terra_init_tmp):
            logger.debug("Cloud-init file changed, replacing old config and executing")
            os.rename(self.terra_final_tmp,self.terra_final)
            os.rename(self.temp_terra_init_tmp,self.temp_terra_init)
            self.execute()
            self.status = "Updated"
            logger.debug("Initialisation changed")
        elif self.tera_data['type'] == "azure" and not self._differentiate(self.terra_var,self.terra_var_tmp):
            logger.debug("Infrastructure file changed, replacing old config and executing")
            os.rename(self.terra_final_tmp,self.terra_final)
            os.rename(self.temp_terra_init_tmp,self.temp_terra_init)
            os.rename(self.terra_var_tmp,self.terra_var)
            self.execute()
            self.status = "Updated"
            logger.debug("Infrastructure changed")
        elif self.tera_data['type'] == "gce" and not self._differentiate(self.terra_var,self.terra_var_tmp):
            logger.debug("Infrastructure file changed, replacing old config and executing")
            os.rename(self.terra_final_tmp,self.terra_final)
            os.rename(self.temp_terra_init_tmp,self.temp_terra_init)
            os.rename(self.terra_var_tmp,self.terra_var)
            self.execute()
            self.status = "Updated"
            logger.debug("Infrastructure changed")
        else:
            self.status = "Updated (nothing to update)"
            logger.info("There are no changes in the Terraform files")
            self._remove_tmp_files

    def _node_data_get_interface(self, node, key):
        """
        Get cloud relevant information from tosca
        """
        interfaces = node.interfaces
        try:
            terra_inf = [inf for inf in interfaces if inf.type == "Terraform"][0]
        except (IndexError, AttributeError):
            logger.debug("No interface for Terraform in {}".format(node.name))
        else:
            cloud_inputs = terra_inf.inputs
            return cloud_inputs["provider"]
        return None


    def _node_data_get_context_section(self,properties):
        """
        Create the cloud-init config file
        """
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
                    node_init = self._get_cloud_init(context["cloud_config"], False, False)
            else:
                if context["append"]:
                    # Append Tosca context to the default config
                    logger.info("Append the TOSCA cloud-config with the default config")
                    node_init = self._get_cloud_init(context["cloud_config"], True, False)
                else:
                    # Use the TOSCA context
                    logger.info("The adaptor will use the TOSCA cloud-config")
                    node_init = self._get_cloud_init(context["cloud_config"], False, True)
        else:
            logger.info("The adaptor will use no cloud-config")
            node_init = self._get_cloud_init(None, False, False)

        utils.dump_order_yaml(node_init, self.temp_terra_init_tmp)

        
    def _node_data_get_ec2_host_properties(self, node, key):
        """
        Get EC2 properties and create node definition
        """
        properties = self._get_host_properties(node)

        self.tera_data.setdefault("region", properties["region_name"].value)
        self.tera_data.setdefault("ami", properties["image_id"].value)
        self.tera_data.setdefault("instance_type", properties["instance_type"].value)
        if properties.get("key_name") is not None:
            self.tera_data.setdefault("key_name", properties["key_name"].value)
        
        self._node_data_get_context_section(properties)
        if properties.get("security_group_ids") is not None:
            security_groups = list()
            security_groups = properties["security_group_ids"].value
            self.tera_data.setdefault("vpc_security_group_ids", security_groups[0])

    def _node_data_get_azure_host_properties(self, node, key):
        """
        Get Azure properties and create node definition
        """
        properties = self._get_host_properties(node)
        self.tera_data.setdefault("subscription_id", properties["subscription_id"].value)
        self.tera_data.setdefault("tenant_id", properties["tenant_id"].value)
        self.tera_data.setdefault("rg_name", properties["rg_name"].value)
        self.tera_data.setdefault("vn_name", properties["vn_name"].value)
        self.tera_data.setdefault("sn_name", properties["sn_name"].value)
        self.tera_data.setdefault("nsg", properties["nw_sec_group"].value)
        self.tera_data.setdefault("vm_size", properties["vm_size"].value)
        self.tera_data.setdefault("image", properties["image"].value)
        self._node_data_get_context_section(properties)
        if properties.get("key_data") is not None:
            self.tera_data.setdefault("key_data", properties["key_data"].value)
        if properties.get("public_ip") is not None:
            self.tera_data.setdefault("pip", properties["public_ip"].value)

    def _node_data_get_gce_host_properties(self, node, key):
        """
        Get GCE properties and create node definition
        """
        properties = self._get_host_properties(node)
        self.tera_data.setdefault("region", properties["region"].value)
        self.tera_data.setdefault("project", properties["project"].value)
        self.tera_data.setdefault("machine_type", properties["machine_type"].value)
        self.tera_data.setdefault("zone", properties["zone"].value)
        self.tera_data.setdefault("image", properties["image"].value)
        self.tera_data.setdefault("network", properties["network"].value)
        self._node_data_get_context_section(properties)
        if properties.get("ssh-keys") is not None:
            self.tera_data.setdefault("ssh-keys", properties["ssh-keys"].value)
           
    def _node_data_get_nova_host_properties(self, node, key):
        """
        Get NOVA properties and create node definition
        """
        properties = self._get_host_properties(node)

        self.tera_data.setdefault("image_id", properties["image_id"].value)
        self.tera_data.setdefault("flavor_id", properties["flavor_id"].value)
        self.tera_data.setdefault("auth_url", properties["auth_url"].value)
        self.tera_data.setdefault("tenant_id", properties["project_id"].value)
        self.tera_data.setdefault("network_name", properties["network_name"].value)
        self.tera_data.setdefault("network_id", properties["network_id"].value)
        self.tera_data.setdefault("key_pair", properties["key_name"].value)
        self._node_data_get_context_section(properties)
        if properties.get("security_groups") is not None:
            security_groups = list()
            security_groups = properties["security_groups"].value
            self.tera_data.setdefault("security_groups", security_groups[0])
    
    def _get_cloud_init(self,tosca_cloud_config,append,override):
        """
        Get cloud-config from MiCADO cloud-init template
        """
        yaml.default_flow_style = False
        default_cloud_config = {}
        with open(self.master_cert, 'r') as p:
            master_file = p.read()
        try:
            with open(self.cloudinit_path, 'r') as f:
                template = jinja2.Template(f.read())
                rendered = template.render(worker_name=self.node_name, master_pem = master_file)
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

    def _init_docker(self):
        """ Initialize docker and get Terraform container """
        self.client = docker.from_env()
        i = 0

        while not self.created and i < 5:
            try:
                self.terraform = self.client.containers.list(filters={'label':'io.kubernetes.container.name=terraform'})[0]
                self.created = True
            except Exception as e:
                i += 1
                logger.error("{0}. Try {1} of 5.".format(str(e), i))
                time.sleep(5)

    def _get_host_properties(self, node):
        """ Get host properties """
        return node.get_properties()

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
                if self.node_name == target.name:
                    logger.debug("policy target match for compute node")
                    properties = policy.get_properties()
                    self.min_instances = properties["min_instances"].value
                    self.max_instances = properties["max_instances"].value

    def _differentiate(self, path, tmp_path):
        """ Compare two files """
        return filecmp.cmp(path, tmp_path)

    def _write_tera_aws(self):
        """ Write Terraform template files for aws"""
        with open(self.auth_data_file, 'r') as stream:
            temp = yaml.safe_load(stream)
        resources = temp.get("resource",{})
        for resource in resources:
            if resource.get("type") == "ec2":
                tmp = resource.get("auth_data")

        f = open(self.terra_final_tmp, "w+")
        f.write("variable \"x\" {\n")
        f.write("  default = \"1\"\n")
        f.write("}\n")
        f.write("\n")
        f.write("provider \"aws\" {\n")
        f.write("  region = \"%s\"\n" % (self.tera_data['region']))
        f.write("  access_key = \"%s\"\n" % (tmp['accesskey']))
        f.write("  secret_key = \"%s\"\n" % (tmp['secretkey']))
        f.write("}\n")
        f.write("\n")
        f.write("resource \"aws_instance\" \"%s\" {\n" % (self.tera_data['name']))
        f.write("  ami = \"%s\"\n" % (self.tera_data['ami']))
        f.write("  instance_type = \"%s\"\n" % (self.tera_data['instance_type']))
        if self.tera_data.get("key_name") is not None:
            f.write("  key_name = \"%s\"\n" % (self.tera_data['key_name']))   
        f.write("  vpc_security_group_ids = [\"%s\",]\n" % (self.tera_data['vpc_security_group_ids']))
        f.write("  user_data = \"${file(\"${path.module}/terrainit.yaml\")}\"\n")
        f.write("  count = var.x\n")
        f.write("}\n")
        f.close()

    def _write_tera_nova(self):
        """ Write Terraform template files for openstack"""
        with open(self.auth_data_file, 'r') as stream:
            temp = yaml.safe_load(stream)
        resources = temp.get("resource",{})
        for resource in resources:
            if resource.get("type") == "nova":
                tmp = resource.get("auth_data")

        f = open(self.terra_final_tmp, "w+")
        f.write("variable \"x\" {\n")
        f.write("  default = \"1\"\n")
        f.write("}\n")
        f.write("\n")
        f.write("provider \"openstack\" {\n")
        f.write("  auth_url = \"%s\"\n" % (self.tera_data['auth_url']))
        f.write("  tenant_id = \"%s\"\n" % (self.tera_data['tenant_id']))
        f.write("  user_name = \"%s\"\n" % (tmp['username']))
        f.write("  password = \"%s\"\n" % (tmp['password']))
        f.write("}\n")
        f.write("\n")
        f.write("resource \"openstack_compute_instance_v2\" \"%s\" {\n" % (self.tera_data['name']))
        f.write("  name = \"%s ${count.index}\"\n" % (self.tera_data['name']))
        f.write("  image_id = \"%s\"\n" % (self.tera_data['image_id']))
        f.write("  flavor_id = \"%s\"\n" % (self.tera_data['flavor_id']))
        f.write("  key_pair = \"%s\"\n" % (self.tera_data['key_pair']))
        f.write("  security_groups = [\"%s\"]\n" % (self.tera_data['security_groups']))
        f.write("  user_data = \"${file(\"${path.module}/terrainit.yaml\")}\"\n")
        f.write("  count = var.x\n")
        f.write("\n")
        f.write("  network {\n")
        f.write("    name = \"%s\"\n" % (self.tera_data['network_name']))
        f.write("    uuid = \"%s\"\n" % (self.tera_data['network_id']))
        f.write("  }\n")
        f.write("}\n")
        f.close()

    def _write_tera_azure(self):
        """ Write Terraform template files for Azure"""
        with open(self.auth_data_file, 'r') as stream:
            temp = yaml.safe_load(stream)
        resources = temp.get("resource",{})
        for resource in resources:
            if resource.get("type") == "azure":
                tmp = resource.get("auth_data")

        f = open(self.terra_var_tmp, "w+")
        f.write("vm_name = \"%s\"\n" % (self.tera_data['name']))
        f.write("subscription_id = \"%s\"\n" % (self.tera_data['subscription_id']))
        f.write("client_id = \"%s\"\n" % (tmp['client_id']))
        f.write("client_secret = \"%s\"\n" % (tmp['client_secret']))
        f.write("tenant_id = \"%s\"\n" % (self.tera_data['tenant_id']))
        f.write("rg_name = \"%s\"\n" % (self.tera_data['rg_name']))
        f.write("vn_name = \"%s\"\n" % (self.tera_data['vn_name']))
        f.write("sn_name = \"%s\"\n" % (self.tera_data['sn_name']))
        f.write("nsg = \"%s\"\n" % (self.tera_data['nsg']))
        f.write("vm_size = \"%s\"\n" % (self.tera_data['vm_size']))
        f.write("image = \"%s\"\n" % (self.tera_data['image']))
        if self.tera_data.get("key_data") is not None:
            f.write("key_data = \"%s\"\n" % (self.tera_data['key_data']))
            linux = True
        if self.tera_data.get("pip") is not None:
            f.write("pip = \"%s\"\n" % (self.tera_data['public_ip']))

        if linux:
            with open(self.terra_azure_lin) as p:
                with open(self.terra_final_tmp, "w+") as p1:
                    for line in p:
                        p1.write(line)
        else:
            with open(self.terra_azure_win) as p:
                with open(self.terra_final_tmp, "w+") as p1:
                    for line in p:
                        p1.write(line)

    def _write_tera_gce(self):
        """ Write Terraform template files for GCE"""
        f = open(self.terra_var_tmp, "w+")
        f.write("vm_name = \"%s\"\n" % (self.tera_data['name']))
        f.write("region = \"%s\"\n" % (self.tera_data['region']))
        f.write("project = \"%s\"\n" % (self.tera_data['project']))
        f.write("machine_type = \"%s\"\n" % (self.tera_data['machine_type']))
        f.write("zone = \"%s\"\n" % (self.tera_data['zone']))
        f.write("image = \"%s\"\n" % (self.tera_data['image']))
        f.write("network = \"%s\"\n" % (self.tera_data['network']))
        if self.tera_data.get("ssh-keys") is not None:
            f.write("ssh-keys = \"%s\"\n" % (self.tera_data['ssh-keys']))

        with open(self.terra_gce) as p:
            with open(self.terra_final_tmp, "w+") as p1:
                for line in p:
                    p1.write(line)

        with open(self.auth_gce) as q:
            with open(self.terra_acc, "w+") as q1:
                for line in q:
                    q1.write(line)

    def _config_file_exists(self):
        """ Check if config file was generated during translation """
        return os.path.exists(self.terra_final)

    def _remove_tmp_files(self):
        """ Remove tmp files generated by the update step """
        try:
            os.remove(self.terra_final_tmp)
            logger.debug("File deleted: {}".format(self.terra_final_tmp))
        except OSError:
            pass
        try:
            os.remove(self.temp_terra_init_tmp)
            logger.debug("File deleted: {}".format(self.temp_terra_init_tmp))
        except OSError:
            pass

       