from .resources import (
    Resource,
    Workload,
    Pod,
    PersistentVolume,
    PersistentVolumeClaim,
    Container,
    Service,
    ConfigMap,
)
from .resources.service import get_port_spec
from . import tosca


def get_translator(node):
    """Gets the required translator object to transform the given TOSCA node

    Args:
        node (toscaparser...NodeTemplate): A toscaparser NodeTemplate object

    Returns:
        Translator: The matching translator object
    """
    # TODO: Use ONLY get_derived when v9 API deprecated
    if (
        tosca.get_derived(node, tosca.NodeType.CONTAINER)
        or node.type.startswith(str(tosca.NodeType.CONTAINER))
        or node.type == "tosca.nodes.MiCADO.Container.Pod.Kubernetes"
    ):
        return WorkloadTranslator
    elif tosca.get_derived(node, tosca.NodeType.CONTAINER_CONFIG):
        return ConfigMapTranslator
    elif tosca.get_derived(node, tosca.NodeType.CONTAINER_VOLUME):
        return VolumeTranslator
    else:
        return CustomTranslator


class Translator:
    """Base class for Kubernetes Translators

    Attributes:
        app: Overall application name
        name: Name of the TOSCA node being translated
        manifest_inputs: Overwriting keys in the manifest
        node_info: namedtuple containing the node's data
    """

    def __init__(self, app, name, node_info):
        """Constructor

        Args:
            app (string): Overall application name
            name (string): Name of the TOSCA node being translated
            node_info (NodeInfo(namedtuple)): Complete data from this node
        """
        self.app = app
        self.name = name
        self.manifest_inputs = node_info.inputs
        self.node_info = node_info

    @classmethod
    def from_toscaparser(cls, app, node, repositories=None):
        """Alternative constructor to generate NodeInfo from toscaparser objects

        Args:
            app (name): Overall application name
            node (toscaparser...NodeTemplate): toscaparser's NodeTemplate
            repositories (dict, optional): ToscaTemplate.repositories object

        Returns:
            Translator: An instance of this class
        """
        node_info = tosca.get_container_info(node, repositories)
        return cls(app, node.name, node_info)

    def build(self):
        """Builds the Kubernetes manifest for the given node

        This should return a list of dict objects representing the manifests
        to be built.

        Raises:
            NotImplementedError: If not implemented by inheriting classes
        """
        raise NotImplementedError


class CustomTranslator(Translator):
    """Builds Kubernetes manifests for custom resources

    """

    def build(self):
        """Builds the Kubernetes manifest for a custom resource

        This mostly relies on the dict input being passed in as manifest_inputs
        to feasibly create any Kubernetes resource manifest

        Returns:
            list of dict: The generated manifest, in a list
        """
        resource = Resource(self.app, self.name, self.manifest_inputs)
        return [resource.build(validate=False)]


class ConfigMapTranslator(Translator):
    """Builds Kubernetes manifests for ConfigMap resources

    """

    def build(self):
        """Builds the manifest for a Kubernetes ConfigMap

        Returns:
            list of dict: The generated manifest, in a list
        """
        config = ConfigMap(
            self.app,
            self.name,
            self.manifest_inputs,
            self.node_info.properties,
        )
        return [config.build()]


class VolumeTranslator(Translator):
    """Builds Kubernetes manifests for PersistentVolumes and Claims

    """

    def build(self):
        """Builds the manifest for a Kubernetes Volume

        Generates the PersistentVolume and PersistentVolumeClaim manifests

        Returns:
            list of dict: A list with generated manifests for PV and PVC
        """
        if "emptyDir" in self.manifest_inputs.get("spec", {}):
            return []
        pv = PersistentVolume(
            self.app,
            self.name,
            self.manifest_inputs,
            self.node_info.properties,
        )
        pvc_spec = pv.pvc_spec
        size = pv.size
        pvc = PersistentVolumeClaim(self.app, pv.name, pvc_spec, size)
        return [pv.build()] + [pvc.build()]


class WorkloadTranslator(Translator):
    """Builds the manifest for Kubernetes Workload objects

    Including: Deployments, StatefulSets, Jobs, Pods, DaemonSets
    """

    def build(self):
        """Builds the manifest for a Kubernetes Workload

        Generates the workload manifest itself, as well as the manifests
        for any Services exposing relevant Pods

        Returns:
            list of dict: A list with the Workload and Service manifests
        """
        pod = self._build_pod()
        pod.add_affinity(self.node_info.hosts)

        containers = self._build_containers()
        pod.add_containers(containers)

        resource = Workload(self.app, self.name, self.manifest_inputs)
        resource.add_pod(pod)

        services = self._build_services(pod.ports, pod.namespace, pod.labels)

        return [resource.build()] + [s.build() for s in services]

    def _build_containers(self):
        """Builds containers for the node """
        containers = [self.node_info] + self.node_info.sidecars
        container_list = []

        for container in containers:

            # TODO: Use ONLY container.type == when v9 API deprecated
            if (
                str(tosca.NodeType.KUBERNETES_POD) in container.type
                or "MiCADO.Container.Pod" in container.type
            ):
                continue

            built_container = Container(container)
            built_container.is_init = (
                tosca.NodeType.INIT_CONTAINER == container.type
            )
            try:
                built_container.build()
            except Exception as err:
                raise ValueError(
                    f"Error while building container {container.name}: {err}"
                ) from err

            container_list.append(built_container)
        return container_list

    def _build_pod(self):
        """Builds the Pod object """
        try:
            return Pod(self.app, self.name)
        except Exception as err:
            raise ValueError(
                f"Error while building pod for {self.name}: {err}"
            ) from err

    def _build_services(self, ports, namespace, labels):
        """Builds Services required by the Pods """
        services = {}

        for port in ports:
            port = get_port_spec(port)
            service_name = port.service_name
            service_type = port.type or "ClusterIP"

            if service_name:
                service = services.get(port.service_name)
            else:
                service_name = self.name.lower()
                service = services.get(service_name)
                if service and service.type != service_type:
                    service = None
                    service_name = f"{self.name}-{service_type}".lower()

            if not service:
                try:
                    service = Service(
                        self.app, service_name, labels, service_type
                    )
                except Exception as err:
                    raise ValueError(
                        f"Error while building service for {self.name}: {err}"
                    ) from err

            if namespace:
                service.update_namespace(namespace)
            service.update_spec(port)
            services[service_name] = service
        return services.values()
