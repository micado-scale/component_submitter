from collections import namedtuple
from enum import Enum
import utils


class Interface:
    KUBERNETES = "Kubernetes"


class Affinity:
    COMPUTE_MATCH = "micado.eu/node_type"
    EDGE_MATCH = "name"


class Prefix:
    NODE = "tosca.nodes.MiCADO"
    MONITOR_POLICY = "tosca.policies.Monitoring.MiCADO"
    NETWORK_POLICY = "tosca.policies.Security.MiCADO.Network"


class NodeType(Enum):
    DOCKER_CONTAINER = "Container.Application.Docker"
    INIT_CONTAINER = "Container.Application.Init"
    CONTAINER_VOLUME = "Container.Volume"
    CONTAINER_CONFIG = "Container.Config"
    CONTAINER = "Container.Application"
    KUBERNETES_POD = "Container.Application.Pod"
    KUBERNETES_RESOURCE = "Kubernetes"
    MICADO_COMPUTE = "Compute"
    MICADO_EDGE = "Edge"

    def __eq__(self, other):
        return (Prefix.NODE + "." + self.value) == other

    def __str__(self):
        return Prefix.NODE + "." + self.value


class NetworkProxy(Enum):
    PASSTHROUGH = "Passthrough"
    PLUG = "L7Proxy"
    SMTP = "SmtpProxy"
    HTTP = "HttpProxy"
    HTTP_URI_FILTER = "HttpURIFilterProxy"
    HTTP_WEBDAV = "HttpWebdavProxy"

    @classmethod
    def values(cls):
        return (member.value for member in cls.__members__.values())

    def __eq__(self, other):
        return (Prefix.NETWORK_POLICY + "." + self.value) == other

    def __str__(self):
        return Prefix.NETWORK_POLICY + "." + self.value


def get_container_info(node, repositories):
    """Check the node name for errors (underscores)

    Returns:
        toscaparser.nodetemplate.NodeTemplate: a deepcopy of a NodeTemplate
    """
    if not repositories:
        repositories = []
    NodeInfo = namedtuple(
        "NodeInfo",
        [
            "name",
            "type",
            "properties",
            "inputs",
            "artifacts",
            "parent",
            "sidecars",
            "mounts",
            "hosts",
            "requirements",
            "repositories",
        ],
    )
    return NodeInfo(
        name=node.name,
        type=node.type,
        properties={x: y.value for x, y in node.get_properties().items()},
        inputs=utils.get_lifecycle(node, Interface.KUBERNETES).get(
            "create", {}
        ),
        artifacts=node.entity_tpl.get("artifacts", {}),
        parent=node.type_definition.defs,
        sidecars=_get_related_nodes(node, NodeType.CONTAINER, repositories),
        mounts=_get_related_mounts(node),
        hosts=_get_related_hosts(node),
        requirements=node.requirements,
        repositories={repo.name: repo.reposit for repo in repositories},
    )


def get_derived(node, tosca_type):
    return node.is_derived_from(tosca_type)


def _get_related_nodes(node, tosca_type, repositories=None):
    # TODO use is_derived_from when v9 API deprecated
    return [
        get_container_info(container, repositories)
        for container in node.related.keys()
        # if container.is_derived_from(tosca_type)
        if container.type.startswith(str(tosca_type))
    ]


def _get_related_mounts(node):
    return {
        "volumes": _get_related_nodes(node, NodeType.CONTAINER_VOLUME),
        "configs": _get_related_nodes(node, NodeType.CONTAINER_CONFIG),
    }


def _get_related_hosts(node):
    return {
        Affinity.COMPUTE_MATCH: [
            host.name
            for host in _get_related_nodes(node, NodeType.MICADO_COMPUTE)
        ],
        Affinity.EDGE_MATCH: [
            host.name
            for host in _get_related_nodes(node, NodeType.MICADO_EDGE)
        ],
    }


def _parent_types(node):
    while True:
        if not hasattr(node, "type"):
            break
        yield node.type
        node = node.parent_type
