from .base import Resource


class Pod(Resource):
    """Stores PodSpec data

        Builds a basic PodSpec object using lifecycle inputs

        Attributes:
            version: Version tag taken from the primary container image
            ports: Port info from the containers
    """

    def __init__(self, app, name):
        """Constructor

        Args:
            app (string): Name of greater application
            name (string): Name of this Pod
        """
        super().__init__(app, name, {})
        self.manifest["metadata"].pop("name", None)
        self.version = ""
        self.ports = []

    @staticmethod
    def _default_manifest():
        """Sets default manifest for Pod - no Kind or apiVersion """
        return {
            "metadata": {},
            "spec": {},
        }

    def add_affinity(self, hosts_dict):
        """Adds a node affinity to the PodSpec

        Modifies the manifest attribute, adding the affinity key to the
        PodSpec, given a dictionary where the key is a required
        MatchExpressions key and the value is a list of hosts by name

        Args:
            hosts_dict (dict): dictionary of MatchExpression keys and names
        """
        for key_to_match, hosts in hosts_dict.items():
            self._add_affinity_to_spec(key_to_match, hosts)

    def add_containers(self, containers):
        """Adds containers to the PodSpec

        Handles mounting volumes, passing labels and properties to the PodSpec,
        passing port info for Pod & Services and getting a version number

        Args:
            containers (list of NodeInfo(namedtuple)): List of containers' info
        """
        for container in containers:
            self._handle_mounts(container)
            if container.is_init:
                self.spec.setdefault("initContainers", []).append(
                    container.spec
                )
                continue
            self._update_pod_labels(container)
            self._update_pod_spec(container)
            self._extract_ports(container)
            self.spec.setdefault("containers", []).append(container.spec)
        self.version = self.labels["app.kubernetes.io/version"]

    def _extract_ports(self, container):
        """Handles containerPort and hostPort, gets port info for services """
        for port in container.ports:
            if isinstance(port, (str, int)):
                port = _handle_docker_port(str(port))
            elif port.get("containerPort"):
                container.spec.setdefault("ports", []).append(port)
                continue

            self.ports.append(port)

    def _update_pod_labels(self, container):
        """Updates Pod labels labels generated or container properties"""
        if not self.labels.get("app.kubernetes.io/version"):
            self.labels["app.kubernetes.io/version"] = container.labels.get(
                "app.kubernetes.io/version"
            )

        for key, value in container.labels.items():
            self.labels.setdefault(key, value)

    def _update_pod_spec(self, container):
        """Updates Pod specific options from Docker container properties """
        if container.pod_opts["grace"]:
            self.spec.setdefault(
                "terminationGracePeriodSeconds", container.pod_opts["grace"]
            )

        if container.pod_opts["pid"] == "host":
            self.spec.setdefault("hostPID", True)

        if container.pod_opts["dns"]:
            dnslist = self.spec.setdefault("dnsConfig", {}).setdefault(
                "nameservers", []
            )
            dnslist += container.pod_opts["dns"]

        if container.pod_opts["dns_search"]:
            dnslist = self.spec.setdefault("dnsConfig", {}).setdefault(
                "searches", []
            )
            dnslist += container.pod_opts["dns_search"]

    def _handle_mounts(self, container):
        """Adds volumes, configs and secrets to the manifest """
        for mount_type, mounts in container.info.mounts.items():
            self._add_mounts(mount_type, mounts, container)

    def _add_mounts(self, mount_type, mounts, container):
        """Adds a list of mounts given type, to Container and Pod specs """
        for mount in mounts:
            name = mount.properties.get("name", mount.name)
            claim_name = mount.inputs.get("metadata", {}).get(
                "name", mount.name
            )

            requirements = container.info.requirements
            read_only = _get_volume_property("read_only", name, requirements)
            path = (
                _get_volume_property("location", name, requirements)
                or _get_path_on_disk(mount.inputs, mount.properties)
                or f"/mnt/volumes/{name}"
            )
            _add_volume_to_container_spec(
                name, container.spec, path, read_only
            )

            volume_spec = _get_volume_spec(
                mount_type, name, mount.inputs, claim_name
            )
            self._add_volume_to_pod_spec(volume_spec)

    def _add_volume_to_pod_spec(self, volume_spec):
        """Adds a given volumeSpec to the PodSpec if it does not exist """
        volumes_list = self.spec.setdefault("volumes", [])
        if volume_spec.get("name") not in [
            vol.get("name") for vol in volumes_list
        ]:
            volumes_list.append(volume_spec)

    def _add_affinity_to_spec(self, key_to_match, hosts):
        """Adds affinity to the PodSpec given a key and list of hosts """
        if not hosts:
            return

        selector = {
            "matchExpressions": [
                {"key": key_to_match, "operator": "In", "values": hosts}
            ]
        }

        self.spec.setdefault("affinity", {}).setdefault(
            "nodeAffinity", {}
        ).setdefault(
            "requiredDuringSchedulingIgnoredDuringExecution", {}
        ).setdefault(
            "nodeSelectorTerms", []
        ).append(
            selector
        )


def _get_path_on_disk(inputs, properties):
    """Returns the path as defined in the volume definition """
    disk_path = ""

    for search in inputs.values():
        try:
            if isinstance(search["path"], str):
                disk_path = search["path"]
                break
        except (KeyError, TypeError):
            pass
    else:
        disk_path = properties.get("path", "")

    return disk_path


def _get_volume_property(key, node_name, container_requirements):
    """Returns a property from the relationship definition of a requirement """
    requirements = [
        required["volume"]
        for required in container_requirements
        if "volume" in required
    ]
    for required in requirements:
        try:
            if required["node"] == node_name:
                return required["relationship"]["properties"][key]
        except (AttributeError, TypeError, KeyError):
            pass

    return False


def _get_volume_spec(mount_type, name, inputs, claim_name):
    """Returns the volume spec to be added to the PodSpec """
    volume_spec = {"name": name}
    if mount_type == "volumes":
        volume_spec.update(_inline_volume_check(inputs, claim_name))
    elif mount_type == "configs":
        volume_spec.update({"configMap": {"name": claim_name}})
    elif mount_type == "secrets":
        volume_spec.update({"secret": {"secretName": claim_name}})
    else:
        raise TypeError(
            f"Mount type '{mount_type}' for {name} "
            "should be one of volumes, configs, secrets"
        )
    return volume_spec


def _inline_volume_check(inputs, claim_name):
    """Returns either an emptyDir or PVC volumeSpec """
    if "emptyDir" in inputs.get("spec", {}):
        return {"emptyDir": {}}
    else:
        return {
            "persistentVolumeClaim": {"claimName": claim_name},
        }


def _add_volume_to_container_spec(name, container_spec, path, read_only):
    """Adds the volume and path to the containerSpec """
    volume_mount = {"name": name, "mountPath": path}
    if read_only:
        volume_mount["readOnly"] = "true"
    container_spec.setdefault("volumeMounts", []).append(volume_mount)


def _handle_docker_port(port):
    """Translates a Docker-Compose style port to a Kubernetes servicePort """
    kube_port = {}
    try:
        kube_port["port"] = port.split(":")[1]
        kube_port["targetPort"] = port.split(":")[0]
    except IndexError:
        kube_port["port"] = port.split(":")[0]

    return kube_port
