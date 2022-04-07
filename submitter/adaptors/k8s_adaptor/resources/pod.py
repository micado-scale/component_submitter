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
        """Adds a list of mounts given type, to Container and Pod specs"""
        for requirement in container.info.requirements:
            volume = requirement.get("volume")
            try:
                properties, mount = _get_volume(volume, mounts)
            except ValueError:
                continue
            
            name = mount.properties.get("name", mount.name)
            claim_name = mount.inputs.get("metadata", {}).get(
                "name", mount.name
            )

            properties["mountPath"] = (
                properties.pop("location", None)
                or _get_path_on_disk(mount.inputs, mount.properties)
                or f"/mnt/volumes/{name}"
            )
            _add_volume_to_container_spec(name, container.spec, properties)

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


def _get_volume(volume, mounts):
    """Returns the info of the volume to mount"""
    if not volume:
        raise ValueError

    if isinstance(volume, str):
        name = volume
        properties = {}
    else:
        name = volume.get("node")
        properties = volume.get("relationship", {}).get("properties")

    [mount] = [
        mount for mount in mounts if mount.name == name.replace("_", "-")
    ]
    return properties, mount


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
    """Returns either an emptyDir, hostPath or PVC volumeSpec """
    if "emptyDir" in inputs.get("spec", {}):
        return {"emptyDir": {}}
    elif "hostPath" in inputs.get("spec", {}):
        return inputs.get("spec")
    else:
        return {
            "persistentVolumeClaim": {"claimName": claim_name},
        }


def _add_volume_to_container_spec(name, container_spec, properties):
    """Adds the volume and path to the containerSpec"""
    volume_mount = {"name": name, **properties}
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
