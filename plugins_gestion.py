import os
import importlib
import pkgutil
import inspect
import logging

from abstracts import Adaptor
import adaptors

logger = logging.getLogger("submitter." + __name__)


class PluginsGestion(object):
    def __init__(self):
        logger.debug("init of the Plugin_Gestion")
        self.plugins = self._load_plugins()

    def _load_plugins(self):
        """search through the plugin folder and import all valid plugin"""
        logger.debug("loading the adaptors")
        plugins = {}
        adaptor_modules = [
            importlib.import_module(name)
            for _, name, ispkg in pkgutil.walk_packages(
                path=adaptors.__path__, prefix=adaptors.__name__ + "."
            )
            if name.endswith("_adaptor") and not ispkg
        ]
        for module in adaptor_modules:
            adaptor_class = {
                name: plugin_class
                for name, plugin_class in inspect.getmembers(module, inspect.isclass)
                if issubclass(plugin_class, Adaptor)
            }
            plugins.update(adaptor_class)

        return plugins

    def get_plugin(self, plugin_name):
        """Given the name of a plugin, returns the plugin's class and an instance of the plugin,
        or (None, None) if the plugin isn't listed in the available plugins."""
        logger.debug("plugin wanted: {}".format(plugin_name))
        try:
            return self.plugins[plugin_name]
        except KeyError as err:
            raise FileNotFoundError(
                "Could not find '{}' in adaptors".format(plugin_name)
            ) from err
