from dataclasses import dataclass
from enum import Enum

from submitter import utils


@dataclass(frozen=True, eq=True)
class NodeInfo:
    """Interface to TOSCA Parser"""

    name: str
    type: str
    properties: dict
    inputs: dict
    artifacts: dict
    parent: dict
    sidecars: list
    mounts: dict
    hosts: dict
    requirements: dict
    repositories: dict

    def __hash__(self):
        return hash((self.name, self.type))


class Interface:
    KUBERNETES = "Kubernetes"


class Affinity:
    COMPUTE_MATCH = "micado.eu/node_type"
    EDGE_MATCH = "kubernetes.io/hostname"


class Prefix:
    NODE = "tosca.nodes.MiCADO"
    MONITOR_POLICY = "tosca.policies.Monitoring.MiCADO"
    NETWORK_POLICY = "tosca.policies.Security.MiCADO.Network"


class NodeType(Enum):
    DOCKER_CONTAINER = "Container.Application.Docker"
    INIT_CONTAINER = "Container.Application.Docker.Init"
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


def get_node_info(node, repositories=None):
    """Check the node name for errors (underscores)

    Returns:
        toscaparser.nodetemplate.NodeTemplate: a deepcopy of a NodeTemplate
    """
    if not repositories:
        repositories = []

    return NodeInfo(
        name=node.name,
        type=node.type,
        properties={x: y.value for x, y in node.get_properties().items()},
        inputs=utils.get_lifecycle(node, Interface.KUBERNETES).get(
            "create", {}
        ),
        artifacts=node.entity_tpl.get("artifacts", {}),
        parent=node.type_definition.defs,
        sidecars=list(
            _get_related_nodes(node, NodeType.CONTAINER, repositories)
        ),
        mounts=_get_related_mounts(node),
        hosts=_get_related_hosts(node),
        requirements=node.requirements,
        repositories={repo.name: repo.reposit for repo in repositories},
    )


def get_derived(node, tosca_type):
    return node.is_derived_from(tosca_type)


def _get_related_nodes(node, tosca_type, repositories=None):
    # TODO use is_derived_from when v9 API deprecated
    return {
        get_node_info(related, repositories): _get_matching_requirement(
            related.name, node.requirements
        )
        for related in node.related.keys()
        if related.is_derived_from(tosca_type)
        or related.type.startswith(str(tosca_type))
    }


def _get_matching_requirement(name, requirements):
    for requirement in requirements:
        inner_dict = requirement[list(requirement)[0]]
        if not isinstance(inner_dict, dict):
            continue
        if not inner_dict["node"] == name:
            continue
        return inner_dict.get("relationship", {}).get("properties", {})
    return {}


def _get_related_mounts(node):
    return {
        "volumes": _get_related_nodes(node, NodeType.CONTAINER_VOLUME),
        "configs": _get_related_nodes(node, NodeType.CONTAINER_CONFIG),
    }


def _get_related_hosts(node):
    return {
        Affinity.COMPUTE_MATCH: [
            host.name.lower()
            for host in list(_get_related_nodes(node, NodeType.MICADO_COMPUTE))
        ],
        Affinity.EDGE_MATCH: [
            host.name.lower()
            for host in list(_get_related_nodes(node, NodeType.MICADO_EDGE))
        ],
    }
