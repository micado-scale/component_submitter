from .base import Resource
from utils import update_get_property


class ConfigMap(Resource):
    """Class for Kubernetes ConfigMaps, extends Resource

    Attributes:
        properties: The data or binaryData of a ConfigMap
    """

    def __init__(self, app_id, name, manifest_inputs, properties):
        """Constructor

        Args:
            app_id (string): App name
            name (string): ConfigMap name
            manifest_inputs (dict): Manifest to build ConfigMap on top of
            properties (dict): Properties passed in from the node definition
        """
        super().__init__(app_id, name, manifest_inputs)

        # Get rid of keys that are not relevant for ConfigMaps
        self.spec = None
        self.manifest["metadata"]["labels"].pop("app.kubernetes.io/version", None)
        self.properties = properties
        self._handle_properties()

    @staticmethod
    def _default_manifest():
        """ Returns the manifest structure for a ConfigMap object

        ConfigMaps don't have the 'spec' key
        """
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {},
        }

    def _handle_properties(self):
        """Updates the data and binaryData of the ConfigMap
        """
        update_get_property([self.manifest], self.properties)
        if not self.manifest.get("binaryData"):
            self.manifest.pop("binaryData", None)
        if not self.manifest.get("data"):
            self.manifest.pop("data", None)
