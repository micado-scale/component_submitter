from .resources import (
    Custom,
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


def get_manifest_type(node):
    """Gets the required manifest object to transform the given TOSCA node

    Args:
        node (toscaparser...NodeTemplate): A toscaparser NodeTemplate object

    Returns:
        Manifest: The matching Manifest object
    """
    MANIFEST_TYPES = {
        tosca.NodeType.CONTAINER: WorkloadManifest,
        tosca.NodeType.CONTAINER_CONFIG: ConfigMapManifest,
        tosca.NodeType.CONTAINER_VOLUME: VolumeManifest,
    }

    for node_type, manifest_type in MANIFEST_TYPES.items():
        if tosca.get_derived(node, node_type):
            return manifest_type

    return CustomManifest


class Manifest:
    """Base class for Kubernetes Manifests

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
            Manifest: An instance of this class
        """
        node_info = tosca.get_node_info(node, repositories)
        return cls(app, node.name, node_info)

    def build(self):
        """Builds the Kubernetes manifest for the given node

        This should return a list of dict objects representing the manifests
        to be built.

        Raises:
            NotImplementedError: If not implemented by inheriting classes
        """
        raise NotImplementedError


class CustomManifest(Manifest):
    """Builds Kubernetes manifests for custom resources

    """

    def build(self):
        """Builds the Kubernetes manifest for a custom resource

        This mostly relies on the dict input being passed in as manifest_inputs
        to feasibly create any Kubernetes resource manifest

        Returns:
            list of dict: The generated manifest, in a list
        """
        resource = Custom(self.app, self.name, self.manifest_inputs)
        resource.add_affinity(self.node_info.hosts)
        return [resource.build(validate=False)]


class ConfigMapManifest(Manifest):
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


class VolumeManifest(Manifest):
    """Builds Kubernetes manifests for PersistentVolumes and Claims

    """

    def build(self):
        """Builds the manifest for a Kubernetes Volume

        Generates the PersistentVolume and PersistentVolumeClaim manifests

        Returns:
            list of dict: A list with generated manifests for PV and PVC
        """
        if is_empty_dir_or_host_path(self.manifest_inputs):
            return []
        
        pv = PersistentVolume(
            self.app,
            self.name,
            self.manifest_inputs,
            self.node_info.properties,
        )
        pvc = PersistentVolumeClaim(
            self.app,
            pv.name,
            pv.pvc_spec,
            pv.size,
        )
        return [pv.build()] + [pvc.build()]


class WorkloadManifest(Manifest):
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
        pod = build_pod(self.app, self.name)
        pod.add_affinity(self.node_info.hosts)

        containers = build_containers(self.node_info)
        pod.add_containers(containers)

        resource = Workload(self.app, self.name, self.manifest_inputs)
        resource.add_pod(pod)

        services = build_services(self.app, self.name, pod)

        return [resource.build()] + [s.build() for s in services]


def build_pod(app, name):
    """Builds the Pod object """
    try:
        return Pod(app, name)
    except Exception as err:
        raise ValueError(
            f"Error while building pod for {name}: {err}"
        ) from err


def build_containers(node_info):
    """Builds containers for the node """
    containers = [node_info] + node_info.sidecars
    container_list = []

    for container in containers:
        if (tosca.NodeType.KUBERNETES_POD in container.type):
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


def build_services(app, name, pod):
    """Builds Services required by the Pods """
    services = {}

    for port in pod.ports:
        port = get_port_spec(port)
        svc_name = port.service_name or name.lower()
        svc_type = port.type or "ClusterIP"

        service = services.get(svc_name)
        if service and service.type != svc_type:
            service = None
            svc_name = f"{name}-{svc_type}".lower()

        if not service:
            try:
                service = Service(app, svc_name, pod.labels, svc_type)
            except Exception as err:
                raise ValueError(f"Error building service for {name}: {err}")

        if pod.namespace:
            service.update_namespace(pod.namespace)
        service.update_spec(port)
        services[svc_name] = service
    return services.values()


def is_empty_dir_or_host_path(manifest):
    """Check if volume is emptyDir or hostPath, which do not require a manifest

    Args:
        manifest (dict): manifest
    """
    volume_spec = manifest.get("spec", {})
    if "emptyDir" in volume_spec or "hostPath" in volume_spec:
        return True
