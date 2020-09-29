from collections import namedtuple
from .pod import Resource


class Service(Resource):
    """Creates a ServiceSpec

    Builds a service to expose a Pod

    Attributes:
        type (string): Type of Service (ClusterIP, NodePort, ExternalIP, etc...)
    """

    def __init__(self, app, name, labels, service_type):
        """Constructor

        Args:
            app (name): Name of encapsulating application
            name (string): Name of this Service resource
            labels (dict): Labels of the Pod to expose
        """
        super().__init__(app, name, {})
        self.labels.pop("app.kubernetes.io/version", None)
        self.spec["selector"] = labels
        self.type = service_type
        if self.type != "ClusterIP":
            self.spec["type"] = self.type

    @staticmethod
    def _default_manifest():
        """Sets the default manifest structure for a Service """
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {},
            "spec": {},
        }

    def update_spec(self, port):
        """ Add a port to the ServiceSpec """
        port_spec = {
            "name": port.name,
            "port": port.port,
            "targetPort": port.target_port,
            "nodePort": port.node_port,
            "protocol": port.protocol,
        }
        port_spec = {k: v for k, v in port_spec.items() if v}
        self.spec.setdefault("ports", []).append(port_spec)
        if port.cluster_ip:
            self.spec.setdefault("clusterIP", port.cluster_ip)

    def update_namespace(self, namespace):
        """ Adjust the namespace of this ServiceSpec """
        self.namespace = namespace
        self.manifest["metadata"]["namespace"] = namespace


def get_port_spec(port):
    """Separate the port spec out of the ServiceSpec

    Args:
        port (dict): The port from the container (PortSpec mixed with ServiceSpec)

    Returns:
        namedtuple: The PortSpec, extracted from the ServiceSpec
    """

    alt_name = (
        str(port.get("port", port.get("targetPort", port.get("target", ""))))
        + "-"
        + port.get("protocol", "tcp").lower()
    )
    alt_type = "NodePort" if port.get("nodePort") else ""
    alt_port = port.get("published", port.get("targetPort", port.get("target")))
    PortSpec = namedtuple(
        "PortSpec",
        [
            "name",
            "service_name",
            "type",
            "node_port",
            "port",
            "protocol",
            "target_port",
            "cluster_ip",
        ],
    )
    port_spec = PortSpec(
        name=port.get("name") or alt_name,
        service_name=port.get("metadata", {}).get("name"),
        type=port.get("type") or alt_type,
        node_port=port.get("nodePort"),
        port=port.get("port") or alt_port,
        protocol=port.get("protocol", "").upper(),
        target_port=port.get("targetPort") or port.get("target"),
        cluster_ip=port.get("clusterIP"),
    )
    return _validate_port_spec(port_spec)


def _validate_port_spec(port):
    """Carry out basic validation of a port

    Checks to see a port & name exist, ClusterIP and NodePort are in range

    Args:
        port (PortSpec(namedtuple)): Port data
    """
    # Make sure we have a port
    if not port.port:
        raise KeyError("Missing 'port' in definition")

    # Make sure the ClusterIP is (kind of) in range
    if port.cluster_ip:
        ip_split = port.cluster_ip.split(".")
        if ip_split[0] == "10" and 96 <= int(ip_split[1]) <= 111:
            pass
        elif ip_split[0] == "None":
            pass
        else:
            raise ValueError(
                f"ClusterIP {port.cluster_ip} is out of range 10.96.x.x - 10.111.x.x"
            )

    # Make sure the NodePort is in range
    if port.node_port:
        if int(port.node_port) < 30000 or int(port.node_port) > 32767:
            raise ValueError(f"nodePort {port.node_port} is out of range 30000-32767")

    return port
