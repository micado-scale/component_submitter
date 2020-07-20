import shlex

# Swarm properties unsupported by Kubernetes and/or this adaptor
SWARM_PROPERTIES = (
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
)


class Container:
    """Class for a container in Kubernetes
    
    Creates a container object to be added to a Kubernetes Pod

    Attributes:
        info: The NamedTuple that describes the container
        name: Name of the container
        spec: Dictionary representation of the container
        labels: Labels to be passed up to the Pod
        pod_opts: PodSpec options to be passed up to the Pod
        is_init: Boolean to indicate an InitContainer
        ports: Port info to be passed up to the Pod, or a Service
    """

    def __init__(self, container_info):
        """Constructor

        Args:
            container_info (NodeInfo(namedtuple)): The available data on a container
        """

        self.info = container_info
        self.name = container_info.name
        self.spec = container_info.properties
        self.labels = {}
        self.ports = {}
        self.pod_opts = {}
        self.is_init = False

    def build(self):
        """ Builds the container spec

        Removes Swarm and/or Pod related keys, determines the container image and 
        translates Swarm properties to Kubernetes conventions
        """
        self._remove_swarm_keys()
        self._remove_pod_keys()
        self._set_image()
        self._translate_docker_properties()

    def _remove_swarm_keys(self):
        """ Removes unsupported Swarm-specific properties """
        for key in SWARM_PROPERTIES:
            self.spec.pop(key, None)

    def _remove_pod_keys(self):
        """ Removes and stores properties required at the Pod level

        This includes labels, port info and certain properties
        """
        self.labels = self.spec.pop("labels", {})
        self.ports = self.spec.pop("ports", [])
        self.pod_opts["grace"] = self.spec.pop("stop_grace_period", None)
        self.pod_opts["pid"] = self.spec.pop("pid", None)
        self.pod_opts["dns"] = self.spec.pop("dns", [])
        self.pod_opts["dns_search"] = self.spec.pop("dns_search", [])

    def _translate_docker_properties(self):
        """ Translate basic Docker properties in the ContainerSpec"""
        self.spec.setdefault("name", self.spec.pop("container_name", self.name))
        self.spec.setdefault("command", shlex.split(self.spec.pop("entrypoint", "")))
        self.spec.setdefault("args", shlex.split(self.spec.pop("cmd", "")))
        self.spec.setdefault("env", _make_env(self.spec.pop("environment", {})))
        self.spec.setdefault("stdin", self.spec.pop("stdin_open", None))
        self.spec.setdefault("workingDir", self.spec.pop("working_dir", None))

        privileged = self.spec.pop("privileged", None)
        if privileged:
            self.spec.setdefault("securityContext", {})
            self.spec["securityContext"].setdefault("privileged", privileged)

        # Clean-up any empty fields
        self.spec = {k: v for k, v in self.spec.items() if v}

    def _set_image(self):
        """Set the Docker image & the version label

        Raises:
            LookupError: Force a rollback when no container image is given
        """

        if not self.spec.get("image"):
            try:
                self.spec["image"] = self._get_image_from_artifact()
            except (AttributeError, KeyError) as err:
                raise LookupError(
                    f"Could not get {self.name} container image: {err}"
                ) from err

        try:
            version = self.spec["image"].split("/")[-1].split(":")[1]
        except IndexError:
            version = "latest"

        self.labels.setdefault("app.kubernetes.io/version", version)

    def _get_image_from_artifact(self):
        """ Determine the image and repo from artifacts, or parent artifacts """
        try:
            image = self.info.artifacts["image"]["file"]
            repository = self.info.artifacts["image"].get("repository")
        except (AttributeError, KeyError):
            parent_artifacts = self.info.parent.get("artifacts", {})
            image = parent_artifacts["image"]["file"]
            repository = parent_artifacts.get("image", {}).get("repository")

        # Default to DockerHub
        if not repository or (
            repository.lower().replace(" ", "").replace("-", "").replace("_", "")
            == "dockerhub"
        ):
            return image

        try:
            path = self.info.repositories[repository]
            path = path.strip("/").replace("https://", "").replace("http://", "")
            image = "/".join([path, image])
        except KeyError:
            raise KeyError(f"Repository {repository} not defined!")
        return image


def _make_env(environment):
    """Change from Docker environment to Kubernetes env

    Args:
        environment (dict): Docker-style environment data

    Returns:
        list: Kubernetes-style env data
    """
    env = []
    for key, value in environment.items():
        env.append({"name": key, "value": value})

    return env
