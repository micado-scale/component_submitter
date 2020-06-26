from .base import Resource
from utils import update_get_property

PVC_SPEC_FIELDS = (
    "accessModes",
    "dataSource",
    "resources",
    "selector",
    "storageClassName",
    "volumeMode",
    "VolumeName",
)


class PersistentVolumeClaim(Resource):
    """Creates a PersistentVolumeClaim

    Builds the manifest for a PVC
    """

    def __init__(self, app_id, name, pvc_spec, size):
        """Constructor

        Args:
            app_id (string): Name of the overall application
            name (string): Name of this claim
            pvc_spec (dict): Inputs to the manifest of the PVC
            size (string): Size with units of volume
        """
        super().__init__(app_id, name, pvc_spec)
        self.manifest["metadata"]["labels"].pop(
            "app.kubernetes.io/version", None
        )
        self._set_pvc_defaults(size)

    @staticmethod
    def _default_manifest():
        """Sets the default structure of the manifest for a PVC """
        return {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {},
            "spec": {},
        }

    def _set_pvc_defaults(self, size):
        """Sets some defaults on the PVC manifest """
        self.spec.setdefault("resources", {}).setdefault(
            "requests", {}
        ).setdefault("storage", size)
        if not self.spec.get("accessModes"):
            self.spec.setdefault("accessModes", []).append("ReadWriteMany")

        # Select the appropriate PV
        self.spec.setdefault("selector", {}).setdefault(
            "matchLabels", {}
        ).update(self.labels)


class PersistentVolume(Resource):
    """Create a PersistentVolume

    Attributes:
        pvc_spec: Dictionary representation of PVC required options
        size: String of size with units for this volume
    """

    def __init__(self, app_id, name, manifest_inputs, properties):
        """Constructor

        Args:
            app_id (string): Name of overall application
            name (string): Name of this PV
            manifest_inputs (dict): Inputs for the PV manifest
            properties (dict): Properties to resolve TOSCA get_property()
        """
        pvc_spec = self._pop_pvc_spec(manifest_inputs)
        super().__init__(app_id, name, manifest_inputs)

        self._clear_pv_fields()
        self.pvc_spec = pvc_spec
        self.size = ""

        update_get_property(self.spec.values(), properties)
        self._set_pv_defaults(properties)

    @staticmethod
    def _default_manifest():
        """Set structure for manifest of a PV """
        return {
            "apiVersion": "v1",
            "kind": "PersistentVolume",
            "metadata": {},
            "spec": {},
        }

    def _clear_pv_fields(self):
        """Remove irrelevant keys from manifest """
        self.labels.pop("app.kubernetes.io/version", None)
        self.manifest["metadata"].pop("namespace", None)
        self.namespace = ""

    def _pop_pvc_spec(self, inputs):
        """Remove and return any PVC specific options in the manifest inputs"""
        pvc_inputs = {
            "accessModes": inputs.get("spec", {}).get("accessModes", [])
        }
        for field in PVC_SPEC_FIELDS:
            try:
                pvc_inputs[field] = inputs.pop(field)
            except KeyError:
                pass
        return {"metadata": inputs.get("metadata", {}), "spec": pvc_inputs}

    def _set_pv_defaults(self, properties):
        """Set some required defaults on the PV manifest """
        self.size = properties.get("size", "1Gi")
        self.spec.setdefault("capacity", {}).setdefault("storage", self.size)

        if not self.spec.get("accessModes"):
            self.spec.setdefault("accessModes", []).append("ReadWriteMany")
        self.spec.setdefault("persistentVolumeReclaimPolicy", "Retain")
