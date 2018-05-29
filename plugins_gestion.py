import os
import imp, inspect, sys
from abstracts import *
from os import path
PATH="{}/adaptors/".format(path.dirname(__file__))
import logging
logger=logging.getLogger("submitter."+__name__)


class PluginsGestion(object):
    def __init__(self):

        logger.debug("init of the Plugin_Gestion")
    def _load_plugins(self):
        """search through the plugin folder and import all valid plugin"""
        logger.debug("loading the adaptors")
        plugins_folder = PATH
        plugins = []
        module_hdl =""
        logger.debug("check if plugin folder is in the sys path")
        if not plugins_folder in sys.path:
            sys.path.append(plugins_folder)
        for root, dirs, files in os.walk(plugins_folder):
            logger.debug("for loop through the plugins files import them")
            for module_file in files:
                module_name, module_extension = os.path.splitext(module_file)
                if module_extension == os.extsep + "py":
                    try:
                        module_hdl, path_name, description = imp.find_module(module_name)
                        logger.debug("trying to import the module {}".format(module_name))
                        plugin_module = imp.load_module(module_name, module_hdl, path_name,
                                                    description)
                        logger.debug("inspect the plugin class {}".format(plugin_module))
                        plugin_classes = inspect.getmembers(plugin_module, inspect.isclass)
                        for plugin_class in plugin_classes:
                            logger.debug("check if {} is subclass of Abstract Adaptor".format(plugin_class))
                            if issubclass(plugin_class[1], Adaptor):
                                # Load only those plugins defined in the current module
                                # (i.e. don't instantiate any parent plugins)
                                if plugin_class[1].__module__ == module_name:
                                    #plugin = plugin_class[1]()
                                    plugins.append(plugin_class)
                    finally:
                        if module_hdl:
                            module_hdl.close()
        return plugins

    def get_plugin(self, plugin_name):
        """Given the name of a plugin, returns the plugin's class and an instance of the plugin,
        or (None, None) if the plugin isn't listed in the available plugins."""
        logger.debug("plugin wanted: {}".format(plugin_name))
        plugin_class = None
        plugin_instance = None
        available_plugins = self._load_plugins()
        plugin_names = [plugin[0] for plugin in available_plugins]
        plugin_classes = [plugin[1] for plugin in available_plugins]
        logger.debug("check if {} is in the plugin list".format(plugin_name))
        if plugin_name in plugin_names:
            plugin_class = plugin_classes[plugin_names.index(plugin_name)]
            #plugin_instance = plugin_class()
            #plugin_instance.data = self.data
        #return plugin_class, plugin_instance
        logger.debug("return {}".format(plugin_class))
        return plugin_class
