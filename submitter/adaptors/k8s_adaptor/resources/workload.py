from .base import Resource


class Workload(Resource):
    """Store Workload data

        Builds a basic workload object using lifecycle inputs

        Attributes:
            pod: The Pod object in this workload
    """

    def __init__(self, app_id, name, manifest_inputs):
        """Constructor

        Prepares the Workload, with Deployment as default Kind

        Args:
            app_id (string): Name of encapsulating application
            name (string): Name of this workload
            manifest_inputs (dict): Exisiting manifest to build upon
        """
        super().__init__(app_id, name, manifest_inputs)
        self.pod = None
        if not self.manifest.get("kind"):
            self.manifest["kind"] = "Deployment"

    @staticmethod
    def _default_manifest():
        """ Returns the default structure of the given resource """
        return {
            "apiVersion": "",
            "kind": "",
            "metadata": {},
            "spec": {},
        }

    def add_pod(self, pod):
        """Adds the pod to the manifest

        Args:
            pod (Pod): Ready Pod object to add to this Workload
        """
        self.pod = pod
        kind = self.manifest.get("kind")
        self._add_pod_to_manifest(kind)
        self._set_version_label()

    def _set_version_label(self):
        """Sets the version label for the Workload """
        if not self.labels.get("app.kubernetes.io/version"):
            self.labels["app.kubernetes.io/version"] = self.pod.version

    def _add_pod_to_manifest(self, kind):
        """Adds pod to the manifest given the Workload Kind """
        if kind == "Pod":
            self.pod.manifest.update(self.spec)
            self.manifest.update(self.pod.manifest)
            return

        self.spec.setdefault("template", {})
        self.spec["template"].setdefault("metadata", {})
        self.spec["template"].setdefault("spec", {})
        self.overwrite_pod_spec()

        if kind != "Job":
            self.spec.setdefault("selector", {"matchLabels": {}})
            self.spec["selector"]["matchLabels"].update(self.pod.labels)

    def overwrite_pod_spec(self):
        nested_update(self.pod.manifest, self.spec["template"])
        self.spec["template"].update(self.pod.manifest)


def nested_update(original_dict, updated_dict):
    for field, values in updated_dict.items():
        try:
            original_dict[field] = nested_update(
                original_dict.get(field, {}), values
            )
        except (KeyError, AttributeError):
            original_dict[field] = values
    return original_dict
