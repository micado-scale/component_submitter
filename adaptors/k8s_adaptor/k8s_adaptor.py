import os
import subprocess
import logging
import filecmp
import copy
import base64
import json

import pykube
from toscaparser.tosca_template import ToscaTemplate

from .specs import (
    Manifest,
    VolumeManifest,
    ConfigMapManifest,
    Container,
    WorkloadManifest,
    ServiceManifest,
)
import utils
from abstracts import base_adaptor
from abstracts.exceptions import AdaptorCritical, TranslateError

logger = logging.getLogger("adaptors." + __name__)

MICADO_NODE_PREFIX = "tosca.nodes.MiCADO"
TOSCA_NODE_TYPES = (
    DOCKER_CONTAINER,
    CONTAINER_VOLUME,
    CONTAINER_CONFIG,
    KUBERNETES_POD,
    KUBERNETES_RESOURCE,
    MICADO_COMPUTE,
    MICADO_EDGE,
) = (
    MICADO_NODE_PREFIX + "." + policy
    for policy in (
        # Docker Container
        "Container.Application.Docker",
        # Volume
        "Container.Volume",
        # ConfigMap
        "Container.Config",
        # Pod
        "Container.Pod.Kubernetes",
        # Bare Kubernetes Resource
        "Kubernetes",
        # Compute
        "Compute",
        #Edge
        "Edge",
    )
)

KUBERNETES_INTERFACE = "Kubernetes"

MICADO_MONITOR_POLICY_PREFIX = "tosca.policies.Monitoring.MiCADO"
MICADO_NETWORK_POLICY_PREFIX = "tosca.policies.Security.MiCADO.Network"
NETWORK_POLICIES = (
    PASSTHROUGH_PROXY,
    PLUG_PROXY,
    SMTP_PROXY,
    HTTP_PROXY,
    HTTP_URI_FILTER_PROXY,
    HTTP_WEBDAV_PROXY,
) = (
    MICADO_NETWORK_POLICY_PREFIX + "." + policy
    for policy in (
        # PfService
        "Passthrough",
        # PlugProxy
        "L7Proxy",
        # SmtpProxy
        "SmtpProxy",
        # HttpProxy
        "HttpProxy",
        # HttpURIFilterProxy
        "HttpURIFilterProxy",
        # HttpWebdavProxy
        "HttpWebdavProxy",
    )
)


class KubernetesAdaptor(base_adaptor.Adaptor):

    """ The Kubernetes Adaptor class
    Carry out a translation from a TOSCA ADT to a Kubernetes Manifest,
    and the subsequent execution, update and undeployment of the translation.
    """

    def __init__(self, adaptor_id, config, dryrun, validate=False, template=None):
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
        self.manifest_path = "{}{}.yaml".format(out_volume, self.ID)
        self.manifest_tmp_path = "{}tmp_{}.yaml".format(out_volume, self.ID)

        sys_volume = self.config.get("system", "system/")
        self.cadvisor_manifest_path = "{}cadvisor.yaml".format(sys_volume)
        self.nodex_manifest_path = "{}nodex.yaml".format(sys_volume)

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
        """ Translate the relevant sections of the ADT into a Kubernetes Manifest """
        logger.info("Translating into Kubernetes Manifests")
        self.status = "Translating..."
        self.manifests = []
        self.tcp_ports = []
        self.ingress_conf = []
        self.ingress_secrets = {}

        for node in self.tpl.nodetemplates:
            if node.type.startswith("tosca.nodes.MiCADO"):
                self._translate_node_templates(node)

        # Look for a monitoring policy and attach default metric exporters to the application
        for policy in self.tpl.policies:
            if policy.type.startswith(MICADO_MONITOR_POLICY_PREFIX):
                self._translate_monitoring_policy(policy)

            if policy.type.startswith(MICADO_NETWORK_POLICY_PREFIX):
                self._translate_security_policy(policy)

        if self.ingress_conf:
            self._deploy_zorp()
            self._manifest_secrets()
            self._manifest_ingress()

        if not self.manifests:
            logger.info(
                "No nodes to orchestrate with Kubernetes. Do you need this adaptor?"
            )
            self.status = "Skipped Translation"
            return

        if not write_files:
            pass
        elif update:
            utils.dump_list_yaml(self.manifests, self.manifest_tmp_path)
        elif self.validate is False:
            utils.dump_list_yaml(self.manifests, self.manifest_path)

        logger.info("Translation complete")
        self.status = "Translated"

    def _translate_node_templates(self, node):
        node = _get_node(node)

        lifecycle = utils.get_lifecycle(node, KUBERNETES_INTERFACE)
        if not lifecycle:
            return

        if node.is_derived_from(DOCKER_CONTAINER):
            manifest = WorkloadManifest(
                self.short_id, node, lifecycle, self.tpl.repositories
            )
        elif node.is_derived_from(KUBERNETES_RESOURCE):
            manifest = Manifest(
                self.short_id, node.name, lifecycle.get("create"), kind="custom"
            )
            self.manifests += [manifest.resource]
            return
        elif node.is_derived_from(CONTAINER_VOLUME):
            manifest = VolumeManifest(self.short_id, node, lifecycle)
        elif node.is_derived_from(CONTAINER_CONFIG):
            manifest = ConfigMapManifest(self.short_id, node, lifecycle)

        self.manifests += manifest.manifests

    def _translate_monitoring_policy(self, policy):
        if policy.get_property_value("enable_container_metrics"):
            self._translate_container_monitoring_policy()

        if policy.get_property_value("enable_node_metrics"):
            self._translate_node_monitoring_policy()

    def _translate_container_monitoring_policy(self):
        try:
            cadvisor = utils.get_yaml_data(self.cadvisor_manifest_path)
            cadvisor["metadata"]["labels"]["app.kubernetes.io/instance"] = self.short_id
            self.manifests.append(cadvisor)
        except FileNotFoundError:
            logger.warning(
                "Could not find cAdvisor manifest at {}".format(
                    self.cadvisor_manifest_path
                )
            )

    def _translate_node_monitoring_policy(self):
        try:
            nodex = utils.get_yaml_data(self.nodex_manifest_path)
            nodex["metadata"]["labels"]["app.kubernetes.io/instance"] = self.short_id
            self.manifests.append(nodex)
        except FileNotFoundError:
            logger.warning(
                "Could not find NodeExporter manifest at {}".format(
                    self.nodex_manifest_path
                )
            )

    def _translate_security_policy(self, policy):
        if policy.type == PASSTHROUGH_PROXY:
            # This should now work as expected
            pass
        elif policy.type in NETWORK_POLICIES:
            self._translate_level7_policy(policy)
        else:
            logger.warning("Unknown network security policy: {}".format(policy.type))

    def _translate_level7_policy(self, policy):
        ingress = {"policy_type": policy.type.split(".")[-1]}
        ingress.update(
            {key: value.value for key, value in policy.get_properties().items()}
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
            if "encryption_key" not in ingress or "encryption_cert" not in ingress:
                error = "Encryption key and/or cert missing for policy {}".format(
                    policy.type
                )
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
        self._manifest_zorp_service_account()
        self._manifest_zorp_cluster_role()
        self._manifest_zorp_role_binding()
        self._manifest_zorp_daemon_set()

    def _manifest_zorp_service_account(self):
        self.manifests.append(
            {
                "apiVersion": "v1",
                "kind": "ServiceAccount",
                "metadata": {
                    "name": "zorp-ingress-service-account",
                    "namespace": "micado-worker",
                    "labels": {
                        "app.kubernetes.io/name": "zorp-ingress-service-account",
                        "app.kubernetes.io/managed-by": "micado",
                        "app.kubernetes.io/version": "1.0",
                    },
                },
            }
        )

    def _manifest_zorp_cluster_role(self):
        self.manifests.append(
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "ClusterRole",
                "metadata": {
                    "name": "zorp-ingress-cluster-role",
                    "labels": {
                        "app.kubernetes.io/name": "zorp-ingress-cluster-role",
                        "app.kubernetes.io/managed-by": "micado",
                        "app.kubernetes.io/version": "1.0",
                    },
                },
                "rules": [
                    {
                        "apiGroups": [""],
                        "resources": [
                            "configmaps",
                            "endpoints",
                            "nodes",
                            "pods",
                            "secrets",
                            "services",
                            "namespaces",
                            "events",
                            "serviceaccounts",
                        ],
                        "verbs": ["get", "list", "watch"],
                    },
                    {
                        "apiGroups": ["extensions"],
                        "resources": ["ingresses", "ingresses/status"],
                        "verbs": ["get", "list", "watch"],
                    },
                ],
            }
        )

    def _manifest_zorp_role_binding(self):
        self.manifests.append(
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "ClusterRoleBinding",
                "metadata": {
                    "name": "zorp-ingress-cluster-role-binding",
                    "namespace": "micado-worker",
                    "labels": {
                        "app.kubernetes.io/name": "zorp-ingress-cluster-role-binding",
                        "app.kubernetes.io/managed-by": "micado",
                        "app.kubernetes.io/version": "1.0",
                    },
                },
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "ClusterRole",
                    "name": "zorp-ingress-cluster-role",
                },
                "subjects": [
                    {
                        "kind": "ServiceAccount",
                        "name": "zorp-ingress-service-account",
                        "namespace": "micado-worker",
                    }
                ],
            }
        )

    def _manifest_zorp_daemon_set(self):
        self.manifests.append(
            {
                "apiVersion": "apps/v1",
                "kind": "DaemonSet",
                "metadata": {
                    "name": "zorp-ingress",
                    "namespace": "micado-worker",
                    "labels": {
                        "run": "zorp-ingress",
                        "app.kubernetes.io/name": "zorp-ingress",
                        "app.kubernetes.io/managed-by": "micado",
                        "app.kubernetes.io/version": "1.0",
                    },
                },
                "spec": {
                    "selector": {"matchLabels": {"run": "zorp-ingress"}},
                    "template": {
                        "metadata": {"labels": {"run": "zorp-ingress"}},
                        "spec": {
                            "serviceAccountName": "zorp-ingress-service-account",
                            "containers": [
                                {
                                    "name": "zorp-ingress",
                                    "image": "balasys/zorp-ingress:1.0",
                                    "args": [
                                        "--namespace=micado-worker",
                                        "--ingress.class=zorp",
                                        "--behaviour=tosca",
                                        "--ignore-namespaces=micado-system,kube-system",
                                    ],
                                    "livenessProbe": {
                                        "httpGet": {"path": "/healthz", "port": 1042}
                                    },
                                    "ports": self._list_ports(),
                                }
                            ],
                        },
                    },
                },
            }
        )

    def _list_ports(self):
        return [
            {"name": "port-" + str(port), "containerPort": port, "hostPort": port}
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

    def _manifest_ingress(self):
        self.manifests.append(
            {
                "apiVersion": "networking.k8s.io/v1beta1",
                "kind": "Ingress",
                "metadata": {
                    "name": "zorp-ingress",
                    "namespace": "micado-worker",
                    "annotations": {
                        "kubernetes.io/ingress.class": "zorp",
                        "zorp.ingress.kubernetes.io/conf": json.dumps(
                            self.ingress_conf
                        ),
                    },
                },
                "spec": {"rules": [{"http": None}]},
            }
        )

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
                "app.kubernetes.io/instance={}".format(self.short_id),
                "-f",
                self.manifest_path,
            ]
        else:
            operation = ["kubectl", "create", "-f", self.manifest_path, "--save-config"]
        try:
            logger.debug("Executing {}".format(operation))
            subprocess.run(operation, stderr=subprocess.PIPE, check=True)

        except subprocess.CalledProcessError as e:
            logger.error("kubectl: {}".format(e.stderr))
            raise AdaptorCritical("kubectl: {}".format(e.stderr))

        logger.info("Kube objects deployed, trying to get outputs...")
        self._get_outputs()
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
            logger.info(
                "No nodes to orchestrate with Kubernetes. Do you need this adaptor?"
            )
            self.status = "Skipped Update"
        elif os.path.exists(self.manifest_path) and filecmp.cmp(
            self.manifest_path, self.manifest_tmp_path
        ):
            logger.debug("No update - removing {}".format(self.manifest_tmp_path))
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
            operation = ["kubectl", "delete", "no", "-l", "micado.eu/node_type"]
            try:
                logger.debug("Undeploy {}".format(operation))
                subprocess.run(operation, stderr=subprocess.PIPE, check=True)
            except subprocess.CalledProcessError:
                logger.debug("Got error deleting nodes")
                error = True

        # Delete resources in the manifest
        operation = ["kubectl", "delete", "-f", self.manifest_path, "--timeout", "90s"]
        try:
            logger.debug("Undeploy {}".format(operation))
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

    def query(self, query):
        """ Query """
        logger.info("Query ID {}".format(self.ID))
        kube_config = pykube.KubeConfig.from_file("~/.kube/config")
        api = pykube.HTTPClient(kube_config)

        if query == "nodes":
            nodes = pykube.Node.objects(api)
            return [x.name for x in nodes.iterator()]
        elif query == "services":
            pods = pykube.Pod.objects(api)
            return [x.name for x in pods.iterator()]

    def _get_outputs(self):
        """Get outputs and their resultant attributes"""
        logger.info("Fetching outputs...")
        for output in self.tpl.outputs:
            node = output.value.get_referenced_node_template()
            if node.is_derived_from(DOCKER_CONTAINER):
                logger.debug("Inspect node: {}".format(node.name))
                query = output.value.attribute_name
                if query == "port":
                    self.output.setdefault(node.name, {})[query] = query_port(node.name)
            else:
                logger.warning("{} is not a Docker container!".format(node.name))

    def _config_file_exists(self):
        """ Check if config file was generated during translation """
        return os.path.exists(self.manifest_path)

    def _skip_check(self):
        if not self._config_file_exists:
            logger.info("No config generated, skipping {} step...".format(self.status))
            self.status = "Skipped"
            return True
        elif self.dryrun:
            logger.info("DRY-RUN: Kubernetes {} in dry-run mode...".format(self.status))
            self.status = "DRY-RUN Deployment"
            return True


def _get_node(node):
    """Check the node name for errors (underscores)

    Returns:
        toscaparser.nodetemplate.NodeTemplate: a deepcopy of a valid node object
    """
    name = node.name
    name_errors = []

    if "_" in name:
        name_errors.append("TOSCA node names")
    if "_" in (node.get_property_value("name") or ""):
        name_errors.append("property: 'name'")
    if "_" in (node.get_property_value("container_name") or ""):
        name_errors.append("property: 'container_name'")

    if name_errors:
        joined_errors = ", ".join(name_errors)
        logger.error(
            "Failed name convention check (underscores) on node: {}".format(name)
        )
        raise AdaptorCritical(
            "Underscores in node {} not allowed for {}".format(name, joined_errors)
        )

    return copy.deepcopy(node)


def query_port(service_name):
    """Queries a specific service for its port listing

    Args:
        service_name (string): Name of service to query

    Returns:
        dict: port listing
    """
    kube_config = pykube.KubeConfig.from_file("~/.kube/config")
    api = pykube.HTTPClient(kube_config)
    try:
        service = pykube.Service.objects(api).get_by_name(service_name)
    except Exception:
        return "Service {} not found".format(service_name)
    return service.obj.get("spec", {}).get("ports", {})
