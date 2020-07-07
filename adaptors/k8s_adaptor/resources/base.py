class Resource:
    """Base class for Kubernetes Resources

    Other Kubernetes objects (Pod/Workload/Volume/etc...) can extend from this
    class. Generates some default keys for the resource, and pre-fills some
    default labels.

    Attributes:
        app: Name of the overall application
        name: Name of this object
        manifest: Dictionary representation of the resource's mainfest
        namespace: Namespace of the object
        spec: Subdictionary representing spec in the manifest
        labels: Subdictionary representing labels in the manifest metadata
    """

    def __init__(self, app, name, manifest_inputs):
        """Constructor

        Args:
            app (string): Application name
            name (string): Name of specific node (container/kube resource)
            manifest_inputs (dict): Inputs to overwrite a Kubernetes manifest
        """
        self.app = app
        self.name = name
        self.namespace = ""
        self.labels = {}
        self.manifest = dict(self._default_manifest(), **manifest_inputs)
        self.spec = self.manifest.get("spec", {})
        self._update_metadata()

    @staticmethod
    def _default_manifest():
        """ Returns the default structure of the given resource """
        return {
            "apiVersion": "",
            "kind": "",
            "metadata": {},
            "spec": {},
        }

    def build(self, validate=True):
        """Builds the manifest for this resource.

        Validates and returns the manifest as a dictionary

        Returns:
            dict: The Kubernetes manifest for this resource
        """
        if validate:
            self._validate()
        return self.manifest

    def _validate(self):
        """Validates a Kubernetes resource (Kind, apiVersion checks)

        Raises:
            ValueError: If unsupported Kind is defined
        """
        kind = self.manifest.get("kind")
        if not kind:
            raise ValueError(
                f"Error validating resource: {self.name}. No Kind provided"
            )
        if not self.manifest.get("apiVersion"):
            try:
                self.manifest["apiVersion"] = get_api(kind)
            except ValueError:
                raise ValueError(
                    f"Error validating resource: {self.name}."
                    f"Unsupported Kind: {kind}"
                )

    def _update_metadata(self):
        """Prepare default name and labels in metadata in the manifest

        This creates labels as per best practice in Kubernetes
        """
        metadata = self.manifest["metadata"]
        self.namespace = metadata.get("namespace", "")
        self.name = metadata.setdefault("name", self.name)
        self.labels = metadata.setdefault("labels", {})
        default_labels = {
            "app.kubernetes.io/name": self.name,
            "app.kubernetes.io/instance": self.app,
            "app.kubernetes.io/managed-by": "micado",
            "app.kubernetes.io/version": "",
        }
        default_labels.update(self.labels)
        self.labels.update(default_labels)


def get_api(kind):
    """Determine the apiVersion for different kinds of resources

    Args:
        kind (string): The name of the resource

    Returns:
        string: the apiVersion for the matching resource

    Raises:
        ValueError: If apiVersion cannot be determined from Kind
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
        if kind == resource:
            return api

    raise ValueError(f"Could not determine apiVersion from {kind}")
