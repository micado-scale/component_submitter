import os
import subprocess
import logging
import filecmp
import copy
import base64
import json

import pykube
from toscaparser.tosca_template import ToscaTemplate

import utils
from abstracts import base_adaptor
from abstracts.exceptions import AdaptorCritical, TranslateError

logger = logging.getLogger("adaptors." + __name__)

TOSCA_TYPES = (
    DOCKER_CONTAINER,
    CONTAINER_VOLUME,
    CONTAINER_CONFIG,
    KUBERNETES_INTERFACE,
    KUBERNETES_POD,
    KUBERNETES_RESOURCE,
    TOSCA_CONTAINER,
    MICADO_COMPUTE,
    MICADO_EDGE,
    MICADO_MONITORING,
    MICADO_SECURITY,
) = (
    "tosca.nodes.MiCADO.Container.Application.Docker",
    "tosca.nodes.MiCADO.Container.Volume",
    "tosca.nodes.MiCADO.Container.Config",
    "Kubernetes",
    "tosca.nodes.MiCADO.Container.Pod.Kubernetes",
    "tosca.nodes.MiCADO.Kubernetes",
    "tosca.nodes.Container.Application",
    "tosca.nodes.MiCADO.Compute",
    "tosca.nodes.MiCADO.Edge",
    "tosca.policies.Monitoring.MiCADO",
    "tosca.policies.Security.MiCADO.Network",
)

SECURITY_POLICIES = (
    PASSTHROUGH_PROXY,
    PLUG_PROXY,
    SMTP_PROXY,
    HTTP_PROXY,
    HTTP_URI_FILTER_PROXY,
    HTTP_WEBDAV_PROXY,
) = (
    # PfService
    "tosca.policies.Security.MiCADO.Network.Passthrough",
    # PlugProxy
    "tosca.policies.Security.MiCADO.Network.L7Proxy",
    # SmtpProxy
    "tosca.policies.Security.MiCADO.Network.SmtpProxy",
    # HttpProxy
    "tosca.policies.Security.MiCADO.Network.HttpProxy",
    # HttpURIFilterProxy
    "tosca.policies.Security.MiCADO.Network.HttpURIFilterProxy",
    # HttpWebdavProxy
    "tosca.policies.Security.MiCADO.Network.HttpWebdavProxy",
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

    def translate(self, update=False):
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
            if policy.type == MICADO_MONITORING:
                self._translate_monitoring_policy(policy)

            if policy.type.startswith(MICADO_SECURITY):
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

        if update:
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

        if node.is_derived_from(KUBERNETES_RESOURCE):
            manifest = Manifest(
                self.short_id, node.name, lifecycle.get("create"), kind="custom"
            )
            self.manifests += [manifest.resource]
            return
        elif node.is_derived_from(CONTAINER_VOLUME):
            manifest = VolumeManifest(self.short_id, node, lifecycle)
        elif node.is_derived_from(CONTAINER_CONFIG):
            manifest = ConfigMapManifest(self.short_id, node, lifecycle)
        else:
            manifest = WorkloadManifest(
                self.short_id, node, lifecycle, self.tpl.repositories
            )

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
        elif policy.type in SECURITY_POLICIES:
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
            if node.is_derived_from(TOSCA_CONTAINER):
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


class Container:
    """Store ContainerSpec data

        Builds a basic ContainerSpec object using node properties

        Args:
            node (toscaparser.nodetemplate.NodeTemplate): The node being built
            repositories (toscaparser.repositories.Repository): The top level repo information
    """

    SWARM_PROPERTIES = [
        "configs",
        "deploy",
        "env_file",
        "expose",
        "extra_hosts",
        "healthcheck",
        "init",
        "logging",
        "networks",
        "secrets",
        "stop_signal",
        "ulimits",
        "volumes",
    ]

    def __init__(self, node, repositories):
        """init the container class with the required properties"""
        self.node = node
        self.repositories = repositories
        self.spec = {k: v.value for k, v in node.get_properties().items()}
        self._build_container_spec()

    def _build_container_spec(self):
        """Remove PodSpec keys and translate basic Docker properties in ContainerSpec"""
        # Remove any swarm-only keys
        for key in self.SWARM_PROPERTIES:
            if self.spec.pop(key, None):
                # logger.warning("Removed Swarm-option {}".format(key))
                pass

        # Remove any PodSpec keys
        self.grace = self.spec.pop("stop_grace_period", None)
        self.pid = self.spec.pop("pid", None)
        self.labels = self.spec.pop("labels", {})
        self.dns = self.spec.pop("dns", [])
        self.dns_search = self.spec.pop("dns_search", [])
        self.ports = self.spec.pop("ports", {})

        # Get image & tag version
        image, version = self._get_image()
        self.spec.setdefault("image", image)
        self.labels.setdefault("app.kubernetes.io/version", version)

        # Translate Docker style properties
        self.spec.setdefault("name", self.spec.pop("container_name", self.node.name))
        self.spec.setdefault("command", self.spec.pop("entrypoint", "").split())
        self.spec.setdefault("args", self.spec.pop("cmd", "").split())
        self.spec.setdefault("env", _make_env(self.spec.pop("environment", {})))
        self.spec.setdefault("stdin", self.spec.pop("stdin_open", None))
        self.spec.setdefault("workingDir", self.spec.pop("working_dir", None))

        privileged = self.spec.pop("privileged", None)
        if privileged:
            self.spec.setdefault("securityContext", {})
            self.spec["securityContext"].setdefault("privileged", privileged)

        # Clean-up any empty fields
        self.spec = {k: v for k, v in self.spec.items() if v}

    def _get_image(self):
        """Return the Docker image & the version tag

        Raises:
            AdaptorCritical: Force a rollback when no container image is given

        Returns:
            tuple: the full path to the Docker image, and the version tag
        """
        # Check top level properties in case someone dislikes TOSCA artifacts
        # image = self.node.get_property_value("image")
        # if image:
        #    try:
        #        version = image.split(":")[1]
        #    except IndexError:
        #        version = "latest"
        #    return image, version

        # Get the Docker image info from this TOSCA node, otherwise from a parent
        try:
            image = self.node.entity_tpl["artifacts"]["image"]["file"]
            repository = self.node.entity_tpl["artifacts"]["image"]["repository"]
        except KeyError:
            image = (
                self.node.type_definition.defs.get("artifacts", {})
                .get("image", {})
                .get("file")
            )
            repository = (
                self.node.type_definition.defs.get("artifacts", {})
                .get("image", {})
                .get("repository")
            )
        # Assume get_property is asking for a property on this node
        # TODO: check which node this is actually looking for
        if isinstance(image, dict):
            key_name = image.get("get_property", [])[-1]
            image = self.spec.pop(key_name, None)

        if not image:
            raise AdaptorCritical("No image specified for {}!".format(self.node.name))

        # Get the version, or set to latest
        try:
            version = image.split(":")[1]
        except IndexError:
            version = "latest"

        if not self.repositories:
            logger.warning("Missing top-level repository info, defaulting to DockerHub")
            return image, version

        # Get the repository URI and build it into the container image path
        repo_name = (
            repository.lower().replace(" ", "").replace("-", "").replace("_", "")
        )
        if repo_name != "dockerhub":
            path = [x.reposit for x in self.repositories if x.name == repository]
            if path:
                image = "/".join([path[0].strip("/"), image])

        return image, version


class Manifest:
    """Store the data generic to all Kubernetes manifests

    Args:
        app_id (string): The ID of the created deployment
        name (string): The name of this component
        spec (dict): User provided spec data, from TOSCA interfaces
        kind (str, optional): The kind of this Kubernetes resource. Defaults to "Deployment".
    """

    def __init__(self, app_id, name, spec, kind="Deployment"):
        """Build the top spec of a Kubernetes manifest"""
        self.name = name
        self.app_id = app_id

        # Create some generic labels based on Kubernetes best practices
        self.labels = {
            "app.kubernetes.io/name": self.name,
            "app.kubernetes.io/instance": self.app_id,
            "app.kubernetes.io/managed-by": "micado",
        }

        # Handle custom Kubernetes resources
        if kind == "custom":
            self.resource = spec
            self.resource.setdefault("metadata", {}).setdefault("labels", {}).update(
                self.labels
            )
            return

        # Build common manifest properties
        self.kind = spec.pop("kind", kind)
        self.namespace = spec.get("metadata", {}).get("namespace")
        self.resource = self._build_resource(spec, self.kind)

    def _build_resource(self, spec, kind):
        """Build the top level spec of this resource

        Args:
            spec (dict): The user provided spec fields
            kind (string): The kind of Kubernetes resource

        Returns:
            dict: A dictionary with the top level manifest fields completed
        """
        resource = {}
        resource["kind"] = kind
        resource["apiVersion"] = spec.pop("apiVersion", _get_api(kind))
        resource["metadata"] = spec.pop("metadata", {})
        if self.namespace:
            resource["metadata"].setdefault("namespace", self.namespace)
        resource["metadata"].setdefault("name", self.name)
        resource["metadata"].setdefault("labels", {}).update(self.labels)
        resource["spec"] = spec.pop("spec", spec)
        return resource


class WorkloadManifest(Manifest):
    """ Stores workload spec data for a manifest

    Args:
        app_id (string): ID of this deployment
        node (toscaparser.nodetemplate.NodeTemplate): TOSCA node object
        lifecycle (dict): User spec inputs from TOSCA interfaces
        repositories (toscaparser.repositories.Repository): Top level TOSCA repository data
    """

    # All possible fields of a Kubernetes PodSpec
    POD_SPEC_FIELDS = (
        "activeDeadlineSeconds",
        "affinity",
        "automountServiceAccountToken",
        "dnsConfig",
        "dnsPolicy",
        "enableServiceLinks",
        "hostAliases",
        "hostIPC",
        "hostNetwork",
        "hostPID",
        "hostname",
        "imagePullSecrets",
        "initContainers",
        "nodeName",
        "nodeSelector",
        "priority",
        "priorityClassName",
        "readinessGates",
        "restartPolicy",
        "runtimeClassName",
        "schedulerName",
        "securityContext",
        "serviceAccount",
        "serviceAccountName",
        "shareProcessNamespace",
        "subdomain",
        "terminationGracePeriodSeconds",
        "tolerations",
        "volumes",
    )

    def __init__(self, app_id, node, lifecycle, repositories):
        """ Builds the manifest for a Kubernetes workload """

        # Builds top level spec with any inputs from the create interface
        workload_spec = lifecycle.get("create", {})
        super().__init__(app_id, node.name, workload_spec)

        self.node = node
        self.repositories = repositories

        # Check if the user has provided PodSpec in create interface inputs
        # Otherwise try to get them from the configure interface inputs
        self.pod = self.resource["spec"].setdefault("template", {})
        if not self.pod:
            pod = lifecycle.get("configure", {})
            self.pod["metadata"] = pod.pop("metadata", {})
            self.pod["spec"] = pod.pop("spec", pod)

        self.containers = []

        # Get properties, if this is a bare pod for hosting containers
        # Otherwise if any normal workload, build the first container
        if self.node.type == KUBERNETES_POD:
            properties = {k: v.value for k, v in node.get_properties().items()}
            self.pod.setdefault("metadata", {}).update(properties.pop("metadata", {}))
            self.pod.setdefault("spec", {}).update(properties)
        else:
            self.containers.append(Container(node, repositories))

        self._add_more_containers()
        self._build_pod()

        # Get ports (to build services) and build volumes from each container
        service_spec_list = []
        for container in self.containers:
            service_spec_list += self._handle_ports(container)
            self._build_volumes(container)

        self.services = {}
        for service_spec in service_spec_list:
            self._build_services(service_spec)

        # Store this workload's manifest along with any services exposing it
        self.manifests = [self.resource] + [x.resource for x in self.services.values()]

    def _add_more_containers(self):
        """Build and add additional containers related to this workload"""
        for node in self.node.related.keys():
            if node.is_derived_from(TOSCA_CONTAINER):
                self.containers.append(Container(node, self.repositories))

    def _build_pod(self):
        """Build the PodSpec for this workload"""
        container_labels = {}

        # Get the labels from each container and add them to our basic labels
        # Reversed so the first added container gets priority
        for container in reversed(self.containers):
            container_labels.update(container.labels)
        pod_labels = {**self.labels, **container_labels}
        self.pod.setdefault("metadata", {}).setdefault("labels", {}).update(pod_labels)

        # Add the generic Kubernetes version label to the top spec
        version = self.pod["metadata"]["labels"]["app.kubernetes.io/version"]
        self.labels["app.kubernetes.io/version"] = version
        self.resource["metadata"]["labels"]["app.kubernetes.io/version"] = version

        # Separate PodSpec data out of the top level resource spec
        pod_data = _separate_data(self.POD_SPEC_FIELDS, self.resource.get("spec", {}))
        self.pod["spec"].update(pod_data)

        # Check for a host requirement, apply it as an affinity
        node_affinity = self._get_hosts()
        self.pod["spec"].update(node_affinity)

        # Get PodSpec fields which may have been defined at the container level
        # Also, add each container to the PodSpec
        for container in self.containers:
            if container.grace:
                self.pod["spec"].setdefault(
                    "terminationGracePeriodSeconds", container.grace
                )
            if container.pid == "host":
                self.pod["spec"].setdefault("hostPID", True)
            if container.dns:
                dnslist = (
                    self.pod["spec"]
                    .setdefault("dnsConfig", {})
                    .setdefault("nameservers", [])
                )
                dnslist += container.dns
            if container.dns_search:
                dnslist = (
                    self.pod["spec"]
                    .setdefault("dnsConfig", {})
                    .setdefault("searches", [])
                )
                dnslist += container.dns_search
            # Add the container to the PodSpec
            self.pod["spec"].setdefault("containers", []).append(container.spec)

        # Handle different workloads
        if self.kind == "Pod":
            self.resource["spec"] = self.pod["spec"]
            self.resource["metadata"] = self.pod["metadata"]
            return
        if self.kind == "Job":
            return

        # Add the selector (for most workloads) pointing at this Pod
        self.resource["spec"].setdefault("selector", {}).setdefault(
            "matchLabels", {}
        ).update(self.pod["metadata"]["labels"])

    def _handle_ports(self, container):
        """Handle docker ports & get individual ServiceSpec dicts for kube ports

        Args:
            container (Container object): The container to extract ports from

        Returns:
            list: A list of ServiceSpec dicts, one for each port
        """
        service_spec_list = []
        ports = container.ports

        for port in ports:

            # Handle Kubernetes container ports
            if port.get("containerPort"):
                container.spec.setdefault("ports", []).append(port)
                continue

            # Handle Docker long syntax ports - host mode
            elif port.get("mode") == "host":
                kube_port = {
                    "containerPort": port.get("target"),
                    "hostPort": port.get("published", port.get("target")),
                }
                container.spec.setdefault("ports", []).append(kube_port)
                continue

            # Handle Docker long syntax ports - ingress mode
            elif port.get("target"):
                _convert_long_port(port)

            # Ports still left at this point are destined for Kubernetes Services
            # Check them and store them in ServiceSpec dictionaries
            port["ports"] = _get_port_spec(port)
            self._validate_port_spec(port)
            service_spec_list.append(port)

        return service_spec_list

    def _build_volumes(self, container):
        """Add volumes / volumeMounts to PodSpec / ContainerSpec

        Args:
            container (Container Object): The container to find volumes for
        """
        requirements = container.node.requirements
        related = container.node.related.keys()

        # Get related volumes or configs to mount to this container
        for node in related:
            if node.is_derived_from(CONTAINER_VOLUME):
                vol_name = node.get_property_value("name") or node.name
                pvc = {"claimName": node.name}
                volume_spec = {"name": vol_name, "persistentVolumeClaim": pvc}

                # Try to build the default path from a path field on the node interface
                [node_spec] = [
                    x.inputs
                    for x in node.interfaces
                    if x.name == "create" and x.type == KUBERNETES_INTERFACE
                ] or [{}]
                vol_path = [x for x in node_spec.values() if "path" in x] or [{}]
                default_path = vol_path[0].get("path") or "/etc/micado/volumes"

            elif node.is_derived_from(CONTAINER_CONFIG):
                vol_name = node.name + "-volume"
                config_vol = {"name": node.name}
                volume_spec = {"name": vol_name, "configMap": config_vol}
                default_path = "/etc/micado/configs"
            else:
                continue

            # Add the volume to the PodSpec if it doesn't exist
            vol_list = self.pod["spec"].setdefault("volumes", [])
            if volume_spec.get("name") not in [x.get("name") for x in vol_list]:
                vol_list.append(volume_spec)

            # Get the path to mount this volume at inside the container
            for requirement in requirements:
                path = None
                volume = requirement.get("volume", {})
                if not volume:
                    continue
                elif isinstance(volume, str):
                    if volume != node.name:
                        continue
                    path = node.get_property_value("path") or default_path
                elif volume.get("node") != node.name:
                    continue
                if not path:
                    path = (
                        (
                            volume.get("relationship", {})
                            .get("properties", {})
                            .get("location")
                        )
                        or node.get_property_value("path")
                        or default_path
                    )
                volume_mount_spec = {"name": vol_name, "mountPath": path}

                # Add the volumeMount to the ContainerSpec
                container.spec.setdefault("volumeMounts", []).append(volume_mount_spec)

    def _build_services(self, service_spec):
        """Join like services together into ServiceManifests

        Args:
            service_spec (dict): A dictionary representation of a Kubernetes ServiceSpec
        """
        port = service_spec.pop("ports", {})
        metadata = service_spec.pop("metadata", {})
        metadata.setdefault("labels", {}).update(self.labels)
        service_namespace = metadata.get("namespace")
        if self.namespace:
            metadata.setdefault("namespace", self.namespace)

        # Set the type and selector inside our ServiceSpec
        service_spec.setdefault("type", "ClusterIP")
        service_spec.setdefault("selector", {}).update(self.pod["metadata"]["labels"])

        # Check for the name of this ServiceSpec,
        # ServiceSpecs with like names are built into a single Service
        service_name = metadata.get("name", None)
        service_type = service_spec.get("type")

        # Otherwise, and if no services exist yet, or if the default-named service
        # (the name of this node) has the same ServiceType as this service then
        # use the default-named service name. Otherwise use a new name based on type.
        if not service_name:
            if (
                not self.services
                or self.services.get(self.name.lower()).type == service_type
            ):
                service_name = self.name.lower()
            else:
                service_name = "{}-{}".format(self.name, service_type).lower()

        # Continue building a service if the name is the same
        # Otherwise, build a new ServiceManifest
        service = self.services.get(service_name)
        if not service:
            service = ServiceManifest(self.app_id, service_name, {"metadata": metadata})
            service.type = service_type

        # Update the spec with fields from this ServiceSpec, and add the new port
        if service_namespace:
            service.update_namespace(service_namespace)
        service.add_spec(service_spec)
        service.add_port(port)
        self.services[service_name] = service

    def _validate_port_spec(self, port):
        """Carry out basic validation of a port

        Checks to see a port & name exist, ClusterIP and NodePort are in range

        Args:
            port (dict): Port data from TOSCA properties
        """
        # Make sure we have a port
        port_spec = port.get("ports", {})
        if not port_spec.get("port"):
            logger.error("No property 'port' (Docker: 'target') given in PortSpec")
            raise TranslateError(
                "No 'port' (Docker: 'target') in {}".format(self.node.name)
            )

        cluster_ip = port.get("clusterIP")
        node_port = port.get("ports", {}).get("nodePort")

        # Make sure the ClusterIP is (kind of) in range
        if cluster_ip:
            ip_split = cluster_ip.split(".")
            if ip_split[0] == "10" and 96 <= int(ip_split[1]) <= 111:
                pass
            elif ip_split[0] == "None":
                pass
            else:
                logger.error("ClusterIP out of range 10.96.x.x - 10.111.x.x")
                raise TranslateError(
                    "ClusterIP {} for {} is out of range".format(
                        cluster_ip, self.node.name
                    )
                )

        # Make sure the NodePort is in range
        if node_port:
            port.setdefault("type", "NodePort")
            if 30000 > int(node_port) or int(node_port) > 32767:
                logger.error("nodePort out of range 30000-32767")
                raise TranslateError(
                    "nodePort {} for {} is out of range".format(
                        node_port, self.node.name
                    )
                )

        # Make sure the port gets a name
        name = "{}-{}".format(
            port_spec.get("port"), port_spec.get("protocol", "tcp").lower()
        )
        port_spec.setdefault("name", name)

    def _get_hosts(self):
        """Finds hosts and builds node affinity for the spec

        Returns:
            dict: NodeAffinity descriptor for the PodSpec
        """
        selector_terms = []
        compute_list = []
        edge_list = []
        for host in self.node.related.keys():
            if host.is_derived_from(MICADO_COMPUTE):
                compute_list.append(host.name)
            elif host.is_derived_from(MICADO_EDGE):
                edge_list.append(host.name)

        compute_selector = {
            "matchExpressions": [
                {
                    "key": "micado.eu/node_type",
                    "operator": "In",
                    "values": compute_list,
                }
            ]
        }
        edge_selector = {
            "matchExpressions": [
                {
                    "key": "name",
                    "operator": "In",
                    "values": edge_list,
                }
            ]
        }
        if compute_list:
            selector_terms.append(compute_selector)
        if edge_list:
            selector_terms.append(edge_selector)
        if not selector_terms:
            return {}

        # Build & return the affinity descriptor
        affinity = {
            "affinity": {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": selector_terms
                    }
                }
            }
        }
        return affinity


class ServiceManifest(Manifest):
    """Store ServiceSpec data for a Service manifest

    Args:
        app_id (string): The ID of this deployment
        name (string): The node name
        spec (dict): The fields to start building this ServiceSpec
    """

    def __init__(self, app_id, name, spec):
        """init this manifest"""
        super().__init__(app_id, name, spec, kind="Service")
        self.type = "ClusterIP"

    def add_port(self, port):
        """ Add a port to the ServiceSpec """
        self.resource.setdefault("spec", {}).setdefault("ports", []).append(port)

    def add_spec(self, spec):
        """ Update the ServiceSpec """
        self.resource.setdefault("spec", {}).update(spec)

    def update_namespace(self, namespace):
        """ Adjust the namespace of this ServiceSpec """
        self.namespace = namespace
        self.resource["metadata"]["namespace"] = namespace


class VolumeManifest(Manifest):
    """Store the data for a PersistentVolume & Claim

    Args:
        app_id (string): ID for this deployment
        node (toscaparser.nodetemplate.NodeTemplate): The node object from toscaparser
        lifecycle (dict): TOSCA interfaces inputs
    """

    def __init__(self, app_id, node, lifecycle):
        """Build the PV & PVC specs into manifests with some defaults"""
        pv_spec, pvc_spec = self._get_specs(lifecycle, node)

        # If no PV spec, only build a PVC (eg. for dynamic volume provisioning)
        if pvc_spec and not pv_spec:
            super().__init__(app_id, node.name, pvc_spec, kind="PersistentVolumeClaim")
            self.manifests = [self.resource]
            return

        # Otherwise, create a PV
        super().__init__(app_id, node.name, pv_spec, kind="PersistentVolume")

        # PVs are not namespaced, if one exists, pass it to the PVC
        pv_namespace = self.resource["metadata"].pop("namespace", None)
        if pv_namespace:
            pvc_spec.setdefault("metadata", {}).setdefault("namespace", pv_namespace)
        self.claim = self._build_resource(pvc_spec, "PersistentVolumeClaim")

        # Set some defaults for these resources
        self.size = node.get_property_value("size") or "1Gi"
        self._set_pv_defaults()
        self._set_pvc_defaults()
        self.manifests = [self.resource, self.claim]

    def _get_specs(self, lifecycle, node):
        """Get PV or PVC inputs from TOSCA interfaces

        Work with the TOSCA get_property function

        Args:
            lifecycle (dict): inputs from TOSCA interfaces
            node (toscaparser.nodetemplate.NodeTemplate): Node object from toscaparser

        Returns:
            tuple: two dicts, PV & PVC specs
        """
        # Assume get_property always refers to node SELF
        # TODO: Allow get_property to get other nodes
        for inputs in lifecycle.values():
            for stage, element in inputs.get("spec", {}).items():
                if not isinstance(element, dict):
                    continue
                for key, val in element.items():
                    if not isinstance(val, dict) or "get_property" not in val:
                        continue
                    element[key] = node.get_property_value(val.get("get_property")[-1])
                # Clean out empty fields
                inputs["spec"][stage] = {k: v for k, v in element.items() if v}

        return lifecycle.get("create", {}), lifecycle.get("configure", {})

    def _set_pv_defaults(self):
        """Set some defaults for PersistentVolumes"""
        spec = self.resource.setdefault("spec", {})
        spec.setdefault("capacity", {}).setdefault("storage", self.size)
        if not spec.get("accessModes"):
            spec.setdefault("accessModes", []).append("ReadWriteMany")
        spec.setdefault("persistentVolumeReclaimPolicy", "Retain")

    def _set_pvc_defaults(self):
        """Set some defaults for PersistentVolumeClaims"""
        spec = self.claim.setdefault("spec", {})
        spec.setdefault("resources", {}).setdefault("requests", {}).setdefault(
            "storage", self.size
        )
        if not spec.get("accessModes"):
            spec.setdefault("accessModes", []).append("ReadWriteMany")

        # Select the appropriate PV
        spec.setdefault("selector", {}).setdefault("matchLabels", {}).update(
            self.labels
        )


class ConfigMapManifest(Manifest):
    """Store the required data for a Kubernetes ConfigMap

    Args:
        app_id (string): ID of this deployment
        node (toscaparser.nodetemplate.NodeTemplate): The node object from toscaparser
        lifecycle (dict): The user inputs from TOSCA interfaces
    """

    def __init__(self, app_id, node, lifecycle):
        """Fill the fields required for a ConfigMap resource"""
        spec = lifecycle.get("create", {})
        super().__init__(app_id, node.name, spec, kind="ConfigMap")
        self.resource.update(self.resource.pop("spec", {}))

        # Assume get_property is asking for a property on this node
        # TODO: check which node this is actually looking for
        if "get_property" in self.resource.get("data", {}):
            key_name = self.resource.get("data").get("get_property", [])[-1]
            self.resource["data"] = node.get_property_value(key_name)

        if "get_property" in self.resource.get("binaryData", ""):
            key_name = self.resource.get("binaryData").get("get_property", [])[-1]
            self.resource["binaryData"] = node.get_property_value(key_name)

        # Remove empty fields
        self.resource = {k: v for k, v in self.resource.items() if v}

        self.manifests = [self.resource]


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


def _get_api(kind):
    """Determine the apiVersion for different kinds of resources

    Args:
        kind (string): The name of the resource

    Returns:
        string: the apiVersion for the matching resource
    """
    # supported workloads & their api versions
    api_versions = {
        "DaemonSet": "apps/v1",
        "Deployment": "apps/v1",
        "Job": "batch/v1",
        "Pod": "v1",
        "ReplicaSet": "apps/v1",
        "StatefulSet": "apps/v1",
        "Ingress": "networking.k8s.io/v1beta1",
        "Service": "v1",
        "PersistentVolume": "v1",
        "PersistentVolumeClaim": "v1",
        "Volume": "v1",
        "Namespace": "v1",
        "ConfigMap": "v1",
    }

    for resource, api in api_versions.items():
        if kind.lower() == resource.lower():
            return api


def _get_port_spec(port):
    """Separate the port spec out of the ServiceSpec

    Args:
        port (dict): The port from the container (PortSpec mixed with ServiceSpec)

    Returns:
        dict: The PortSpec, extracted from the ServiceSpec
    """
    port_spec = {}
    port_spec["name"] = port.pop("name", None)
    port_spec["nodePort"] = port.pop("nodePort", None)
    port_spec["port"] = port.pop("port", None)
    port_spec["protocol"] = port.pop("protocol", None)
    port_spec["targetPort"] = port.pop("targetPort", None)

    # Clean up any unused fields in the PortSpec
    return {k: v for k, v in port_spec.items() if v}


def _convert_long_port(port):
    """Convert a long syntax Docker port (not host mode) to Kubernetes

    Args:
        port (dict): The port spec to reconfigure
    """
    # Rename published (Docker) to port (Kubernetes)
    # If no published, use target (Docker) instead
    rename_key(port, "published", "port")
    if not port.get("port"):
        port["port"] = port.pop("target", None)

    # Rename target (Docker) to targetPort (Kubernetes)
    # Get rid of mode and uppercase the protocol
    rename_key(port, "target", "targetPort")
    port.pop("mode", None)
    if port.get("protocol"):
        port["protocol"] = port.get("protocol").upper()


def rename_key(dicti, old_key, new_key):
    """Rename a dictionary key, if it exists

    Args:
        dicti (dict): The dictionary to mangle
        old_key (string): The old key name
        new_key (string): The new key name
    """
    if dicti.get(old_key):
        dicti.setdefault(new_key, dicti.pop(old_key))


def _make_env(environment):
    """Change from Docker environment to Kubernetes env

    Args:
        environment (dict): Docker-style environment data

    Returns:
        list: Kubernetes-style env data
    """
    if not environment:
        return []

    env = []
    for key, value in environment.items():
        env.append({"name": key, "value": value})

    return env


def _separate_data(key_names, spec_dict):
    """Remove some keys (and their values) from a dictionary

    Args:
        key_names (list): Key names for removal
        spec_dict (dict): Dictionary to remove keys from

    Returns:
        dict: The newly cleaned out dictionary
    """
    data = {}
    for x in key_names:
        try:
            data[x] = spec_dict.pop(x)
        except KeyError:
            pass

    return data


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
