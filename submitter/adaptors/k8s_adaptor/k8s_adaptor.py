import os
import subprocess
import logging
import filecmp
import copy
import base64
import json
import kubernetes_validate
from kubernetes_validate.utils import (
    SchemaNotFoundError,
    VersionNotSupportedError,
    InvalidSchemaError,
    ValidationError,
)

from toscaparser.tosca_template import ToscaTemplate

from submitter import utils
from submitter.abstracts import base_adaptor
from submitter.abstracts.exceptions import AdaptorCritical, TranslateError
from .zorp import ZorpManifests
from .manifest import get_manifest_type
from .tosca import Prefix, NodeType, Interface, NetworkProxy

logger = logging.getLogger("adaptors.k8s_adaptor")


class KubernetesAdaptor(base_adaptor.Adaptor):

    """ The Kubernetes Adaptor class
    Carry out a translation from a TOSCA ADT to a Kubernetes Manifest,
    and the subsequent execution, update and undeployment of the translation.
    """

    def __init__(
        self, adaptor_id, config, dryrun, validate=False, template=None
    ):
        """ init method of the Adaptor """
        super().__init__()

        logger.debug("Initialising Kubernetes Adaptor class...")
        self.status = "Initialising..."

        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")

        self.ID = adaptor_id
        self.dryrun = dryrun
        self.short_id = "_".join(adaptor_id.split("_")[:-1]) or adaptor_id
        self.config = config
        self.tpl = template

        out_volume = self.config.get("volume", "files/output_configs")
        self.manifest_path = f"{out_volume}{self.ID}.yaml"
        self.manifest_tmp_path = f"{out_volume}tmp_{self.ID}.yaml"

        sys_volume = self.config.get("system", "system/")
        self.cadvisor_manifest_path = f"{sys_volume}cadvisor.yaml"
        self.nodex_manifest_path = f"{sys_volume}nodex.yaml"

        self.manifests = []
        self.services = []
        self.volumes = {}
        self.output = {}
        self.tcp_ports = []
        self.ingress_conf = []
        self.ingress_secrets = {}
        self.validate = validate
        logger.info("Kubernetes Adaptor is ready.")
        self.status = "Initialised"

    def translate(self, update=False, write_files=True):
        """ Translate sections of the ADT into a Kubernetes Manifest """
        logger.info("Translating into Kubernetes Manifests")
        self.status = "Translating..."
        self.manifests = []
        self.tcp_ports = []
        self.ingress_conf = []
        self.ingress_secrets = {}

        for node in self.tpl.nodetemplates:
            if node.type.startswith("tosca.nodes.MiCADO"):
                self._translate_node_templates(node)

        # Look for a monitoring policy and attach default
        # metric exporters to the application
        for policy in self.tpl.policies:
            if policy.type.startswith(Prefix.MONITOR_POLICY):
                self._translate_monitoring_policy(policy)

            if policy.type.startswith(Prefix.NETWORK_POLICY):
                self._translate_security_policy(policy)

        if self.ingress_conf:
            self._deploy_zorp()
            self._manifest_secrets()

        if not self.manifests:
            logger.info("No nodes to orchestrate with Kubernetes. Skipping")
            self.status = "Skipped Translation"
            return

        unvalidated_kinds = self.config.get("unvalidated_kinds", [])
        k8s_version = self.config.get("k8s_version", "1.18.0")
        for manifest in self.manifests:
            if manifest["kind"] in unvalidated_kinds:
                continue
            try:
                kubernetes_validate.validate(manifest, k8s_version, strict=True)
            except ValidationError as err:
                message = f"Invalid K8s Manifest: {err.message}"
                logger.error(message)
                raise AdaptorCritical(message) from None
            except (InvalidSchemaError, SchemaNotFoundError):
                message = (
                    f"Schema for {manifest['apiVersion']}/{manifest['kind']} "
                    f"not found in Kubernetes v{k8s_version}"
                )
                logger.error(message)
                raise AdaptorCritical(message) from None
            except VersionNotSupportedError:
                pass

        if not write_files:
            pass
        elif update:
            utils.dump_list_yaml(self.manifests, self.manifest_tmp_path)
        elif self.validate is False:
            utils.dump_list_yaml(self.manifests, self.manifest_path)

        logger.info("Translation complete")
        self.status = "Translated"

    def _translate_node_templates(self, node):
        _name_check_node(node)
        node = copy.deepcopy(node)
        manifests = []

        if not utils.check_lifecycle(node, Interface.KUBERNETES):
            return

        manifest_type = get_manifest_type(node)
        manifest = manifest_type.from_toscaparser(
            self.short_id, node, self.tpl.repositories
        )

        manifests = manifest.build()
        self.manifests += manifests

    def _translate_monitoring_policy(self, policy):
        if policy.get_property_value("enable_container_metrics"):
            self._translate_container_monitoring_policy()

        if policy.get_property_value("enable_node_metrics"):
            self._translate_node_monitoring_policy()

    def _translate_container_monitoring_policy(self):
        try:
            cadvisor = utils.get_yaml_data(self.cadvisor_manifest_path)
            cadvisor["metadata"]["labels"][
                "app.kubernetes.io/instance"
            ] = self.short_id
            self.manifests.append(cadvisor)
        except FileNotFoundError:
            logger.warning(
                "Could not find cAdvisor manifest"
                f" at {self.cadvisor_manifest_path}"
            )

    def _translate_node_monitoring_policy(self):
        try:
            nodex = utils.get_yaml_data(self.nodex_manifest_path)
            nodex["metadata"]["labels"][
                "app.kubernetes.io/instance"
            ] = self.short_id
            self.manifests.append(nodex)
        except FileNotFoundError:
            logger.warning(
                "Could not find NodeExporter manifest"
                f" at {self.nodex_manifest_path}"
            )

    def _translate_security_policy(self, policy):
        if policy.type == str(NetworkProxy.PASSTHROUGH):
            # This should now work as expected
            pass
        elif policy.type in NetworkProxy.values():
            self._translate_level7_policy(policy)
        else:
            logger.warning(f"Unknown network security policy: {policy.type}")

    def _translate_level7_policy(self, policy):
        ingress = {"policy_type": policy.type.split(".")[-1]}
        ingress.update(
            {
                key: value.value
                for key, value in policy.get_properties().items()
            }
        )
        self._extract_ports(ingress)
        self._translate_tls_secrets(ingress, policy)
        self.ingress_conf.append(ingress)

    def _extract_ports(self, ingress):
        try:
            self.tcp_ports.extend(ingress["target_ports"])
        except KeyError:
            pass

    def _translate_tls_secrets(self, ingress, policy):
        if ingress.get("encryption", False):
            if (
                "encryption_key" not in ingress
                or "encryption_cert" not in ingress
            ):
                error = f"Key and/or cert missing for policy {policy.type}"
                logger.error(error)
                raise TranslateError(error)
            index = "krumpli" + str(len(self.ingress_secrets))
            self.ingress_secrets[index] = {
                "tls.key": ingress["encryption_key"],
                "tls.crt": ingress["encryption_cert"],
            }
            ingress["encryption_key"] = index
            ingress["encryption_cert"] = index
        else:
            try:
                del ingress["encryption_key"]
                del ingress["encryption_cert"]
            except KeyError:
                pass

    def _deploy_zorp(self):
        zorp = ZorpManifests()
        ports_list = self._list_ports()
        ingress_conf = json.dumps(self.ingress_conf)

        self.manifests.append(zorp.service_account())
        self.manifests.append(zorp.cluster_role())
        self.manifests.append(zorp.role_binding())
        self.manifests.append(zorp.daemon_set(ports_list))
        self.manifests.append(zorp.ingress(ingress_conf))

    def _list_ports(self):
        return [
            {
                "name": "port-" + str(port),
                "containerPort": port,
                "hostPort": port,
            }
            for port in self.tcp_ports
        ]

    def _manifest_secrets(self):
        for name, secret in self.ingress_secrets.items():
            self.manifests.append(self._k8s_secret(name, secret))

    def _k8s_secret(self, name, secret):
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": name, "namespace": "micado-worker"},
            "type": "Opaque",
            "data": {
                key: base64.b64encode(value.encode("UTF-8")).decode("ASCII")
                for key, value in secret.items()
            },
        }

    def execute(self, update=False):
        """ Execute """
        logger.info("Executing Kubernetes Manifests...")
        self.status = "executing..."

        if self._skip_check():
            return

        if update:
            operation = [
                "kubectl",
                "apply",
                "--prune",
                "-l",
                f"app.kubernetes.io/instance={self.short_id}",
                "-f",
                self.manifest_path,
            ]
        else:
            operation = [
                "kubectl",
                "create",
                "-f",
                self.manifest_path,
                "--save-config",
            ]
        try:
            logger.debug(f"Executing {operation}")
            subprocess.run(operation, stderr=subprocess.PIPE, check=True)

        except subprocess.CalledProcessError as e:
            logger.error(f"kubectl: {e.stderr}")
            raise AdaptorCritical(f"kubectl: {e.stderr}")

        #logger.info("Kube objects deployed, trying to get outputs...")
        #self._get_outputs()
        logger.info("Execution complete")
        self.status = "Executed"

    def update(self):
        """ Update """
        logger.info("Updating Kubernetes Manifests")
        self.status = "Updating..."

        logger.debug("Creating tmp translation...")
        self.manifests = []
        self.translate(True)

        if not self.manifests and self._config_file_exists():
            self.undeploy(False)
            self.cleanup()
            logger.info("Updated (removed all Kubernetes workloads)")
            self.status = "Updated (removed all Kubernetes workloads)"
        elif not self.manifests:
            logger.info("No nodes to orchestrate with Kubernetes. Skipping...")
            self.status = "Skipped Update"
        elif os.path.exists(self.manifest_path) and filecmp.cmp(
            self.manifest_path, self.manifest_tmp_path
        ):
            logger.debug(f"No update - removing {self.manifest_tmp_path}")
            os.remove(self.manifest_tmp_path)
            logger.info("Nothing to update")
            self.status = "Updated (nothing to update)"
        else:
            logger.debug("Updating Kubernetes workloads")
            os.rename(self.manifest_tmp_path, self.manifest_path)
            self.execute(True)
            logger.info("Update complete")
            self.status = "Updated"

    def undeploy(self, kill_nodes=True):
        """ Undeploy """
        logger.info("Undeploying Kubernetes workloads")
        self.status = "Undeploying..."
        error = False

        if self._skip_check():
            return

        if kill_nodes:
            # Delete nodes from the cluster
            operation = [
                "kubectl",
                "delete",
                "no",
                "-l",
                "micado.eu/node_type",
            ]
            try:
                logger.debug(f"Undeploy {operation}")
                subprocess.run(operation, stderr=subprocess.PIPE, check=True)
            except subprocess.CalledProcessError:
                logger.debug("Got error deleting nodes")
                error = True

        # Delete resources in the manifest
        operation = [
            "kubectl",
            "delete",
            "-f",
            self.manifest_path,
            "--timeout",
            "90s",
        ]
        try:
            logger.debug(f"Undeploy {operation}")
            subprocess.run(operation, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError:
            logger.debug("Had some trouble removing Kubernetes workloads...")
            error = True

        if error:
            raise AdaptorCritical("Had some trouble removing workloads!")
        logger.info("Undeployment complete")
        self.status = "Undeployed"

    def cleanup(self):
        """ Cleanup """
        logger.info("Cleaning-up...")
        self.status = "cleaning-up..."

        try:
            os.remove(self.manifest_path)
        except OSError:
            logger.warning("Could not remove manifest file")

        self.status = "Clean!"


    def _get_outputs(self):
        """Get outputs and their resultant attributes"""
        logger.info("Fetching outputs...")
        for output in self.tpl.outputs:
            node = output.value.get_referenced_node_template()
            # TODO Use ONLY is_derived_from when v9 API deprecated
            if node.is_derived_from(
                NodeType.DOCKER_CONTAINER
            ) or node.type.startswith(str(NodeType.DOCKER_CONTAINER)):
                logger.debug(f"Inspect node: {node.name}")
                query = output.value.attribute_name
                if query == "port":
                    pass # TODO: find ports using K8s-py
            else:
                logger.warning(f"{node.name} is not a Docker container!")

    def _config_file_exists(self):
        """ Check if config file was generated during translation """
        return os.path.exists(self.manifest_path)

    def _skip_check(self):
        if not self._config_file_exists:
            logger.info(f"No config generated, skipping {self.status} step...")
            self.status = "Skipped"
            return True
        elif self.dryrun:
            logger.info(
                f"DRY-RUN: Kubernetes {self.status} in dry-run mode..."
            )
            self.status = "DRY-RUN Deployment"
            return True


def _name_check_node(node):
    errors = []
    if "_" in (node.get_property_value("name") or ""):
        errors.append("property: 'name'")
    if "_" in (node.get_property_value("container_name") or ""):
        errors.append("property: 'container_name'")

    if errors:
        errors = ", ".join(errors)
        logger.error(
            f"Failed name convention check (underscores) on node: {node.name}"
        )
        raise AdaptorCritical(
            f"Underscores in properties of {node.name} not allowed for {errors}"
        )
