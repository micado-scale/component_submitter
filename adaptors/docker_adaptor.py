"""
component_submitter.docker_adaptor
----------------------------------

A TOSCA to Docker (Swarm) adaptor.
"""

import logging
import subprocess
import os
import json

import utils
from abstracts import container_orchestrator as abco
from abstracts.exceptions import AdaptorError
from abstracts.exceptions import AdaptorCritical

logger = logging.getLogger("adaptors."+__name__)

DOCKER_THINGS = (DOCKER_CONTAINER, DOCKER_NETWORK, DOCKER_VOLUME, DOCKER_IMAGE,
                 CONNECT_PROP, ATTACH_PROP) = \
                ("tosca.nodes.MiCADO.Container.Application.Docker",
                 "tosca.nodes.MiCADO.network.Network.Docker",
                 "tosca.nodes.MiCADO.Volume.Docker",
                 "tosca.artifacts.Deployment.Image.Container.Docker",
                 "network","location")

class DockerAdaptor(abco.ContainerAdaptor):

    """ The Docker adaptor class

    Carries out the deployment of a Dockerised application or application stack
    based on a description of an application provided by a YAML file which
    follows the OpenStack TOSCA language specification.

    Implements abstract methods ``translate``, ``execute`` and ``undeploy``.

    Usage:
        >>> from docker_adaptor import DockerAdaptor
        >>> container_adapt = DockerAdaptor()
        >>> container_adapt.translate(<path_to_tosca_yaml>)
        <UNIQUE_ID>
        >>> container_adapt.execute(<UNIQUE_ID>)
        (Stack deployed)
        >>> container_adapt.undeploy(<UNIQUE_ID>)
        (Stack undeployed)

    """

    def __init__(self, template = None, adaptor_id = None):
        logger.debug("Initialise the Docker adaptor")
        super().__init__()
        self.compose_data = {}

        if adaptor_id is None:
            self.ID = utils.id_generator()
        else:
            self.ID = adaptor_id

        self.template = template
        logger.info("DockerAdaptor ready to go!")

    def translate(self):
        """ Translate the self.template subset to the Compose format

        Does the work of mapping the Docker relevant sections of TOSCA into a
        dictionary following the Docker-Compose format, then dumping output to
        a .yaml file in output_configs/

        :raises: AdaptorCritical
        """

        logger.info("Starting translation...")
        self.compose_data = {"version":"3.4"}

        for tpl in self.template.nodetemplates:
            if DOCKER_CONTAINER in tpl.type:
                self._get_properties(tpl, "services")
                self._get_artifacts(tpl, self.template.repositories)

        if not self.compose_data.get("services"):
            logger.error("No TOSCA nodes of Docker type!")
            raise AdaptorCritical("No TOSCA nodes of Docker type!")

        for tpl in self.template.nodetemplates:
            if DOCKER_CONTAINER in tpl.type:
                self._get_requirements(tpl)
            elif DOCKER_NETWORK in tpl.type:
                self._get_properties(tpl, "networks")
            elif DOCKER_VOLUME in tpl.type:
                self._get_properties(tpl, "volumes")

        utils.dump_order_yaml(self.compose_data, "files/output_configs/{}.yaml".format(self.ID))


    def execute(self):
        """ Deploy the stack onto the Swarm

        Executes the `docker stack deploy` command on the Docker-Compose file
        created in `translate()`

        :raises: AdaptorCritical
        """
        logger.info("Starting Docker execution...")
        try:
            #subprocess.run(["docker", "stack", "deploy", "--compose-file",
            # "output_configs/{}.yaml".format(self.ID), self.ID], check=True)
            logger.info("subprocess.run([\"docker\", \"stack\", \"deploy\", "
             "\"--compose-file\", \"docker-compose.yaml\", {}], check=True)".format(self.ID))
        except subprocess.CalledProcessError:
            logger.error("Cannot execute Docker")
            raise AdaptorCritical("Cannot execute Docker")
        logger.info("Docker running, trying to get outputs...")
        #self._get_outputs()

    def undeploy(self):
        """ Undeploy the stack from Docker

        Runs `docker stack down` on the specified stack, removes the associated
        Docker-Compose file from output_configs/

        :raises: AdaptorCritical

        """
        logger.info("Undeploying the application")
        try:
            #subprocess.run(["docker", "stack", "down", self.ID], check=True)
            logger.debug("Undeploy application with ID: {}".format(self.ID))
        except subprocess.CalledProcessError:
            logger.error("Cannot undeploy the stack")
            raise AdaptorCritical("Cannot undeploy the stack")
        logger.info("Stack is down...")

    def cleanup(self):
        """ Cleanup is a method that removes the associated Docker-Compose file from
        files/output_configs/

        .. note::
          A warning will be logged if the Compose file cannot be remove
        """
        logger.info("Cleanup config for ID {}".format(self.ID))
        try:
            os.remove("files/output_configs/{}.yaml".format(self.ID))
        except OSError as e:
            logger.warning(e)

    def update(self):

        #TODO create this function
        pass
    def _get_outputs(self):
        """ Get outputs and their resultant attributes """

        def get_attribute(service, query):
            """ Get attribute from a service """
            try:
                inspect = subprocess.check_output(
                                    ["docker", "service", "inspect", service] )
                [inspect] = json.loads(inspect.decode('UTF-8'))
            except (subprocess.CalledProcessError, TypeError):
                logger.warning("Cannot inspect the service {}".format(service))
            else:
                if query == "ip_address":
                    result = inspect.get("Endpoint").get("VirtualIPs")
                elif query == "port":
                    result = inspect.get("Endpoint").get("Ports")

                logger.info("[OUTPUT] Service: <{}> Attr: <{}>\n  RESULT: {}"
                            .format(service, query, result))

        for output in outputs:
            node = output.value.get_referenced_node_template()
            if node.type == DOCKER_CONTAINER:
                service = "{}_{}".format(self.ID, node.name)
                logger.debug("Inspect service: {}".format(service))
                query = output.value.attribute_name
                #get_attribute(service, query)


    def _get_properties(self, node, key):
        """ Get TOSCA properties """
        properties = node.get_properties()
        entry = {node.name: {}}

        for property in properties:
            try:
                entry[node.name][property] = node.get_property_value(property).result()
            except AttributeError as e:
                logger.debug("Error caught {}, trying without .result()".format(e))
                entry[node.name][property] = node.get_property_value(property)

        # Write the compose data
        self._create_compose_properties(key, entry)

    def _get_artifacts(self, tpl, repositories):
        """ Get TOSCA artifacts """
        artifacts = tpl.entity_tpl.get("artifacts").values()
        for artifact in artifacts:
            if DOCKER_IMAGE in artifact.get("type"):
                break
        else:
            raise AdaptorCritical("No artifact of type <{}>".format(DOCKER_IMAGE))

        repository = artifact.get("repository")
        if repository and "docker_hub" not in repository:
            for repo in repositories:
                if repository == repo.name:
                    repository = repo.reposit
                    break
        else:
            repository = ""

        image = artifact["file"]
        image = "{}{}".format(repository, image)

        # Write the compose data
        self._create_compose_image(tpl.name, image)

    def _get_requirements(self, tpl):
        """ Get TOSCA requirements """
        for requirement in tpl.requirements:
            req_vals = list(requirement.values())[0]
            related_node = req_vals["node"]

            #disable HostedOn until fully implemented
            if "HostedOn" in str(req_vals):
                #self._create_compose_constraint(tpl.name, related_node)
                pass
            elif "ConnectsTo" in str(req_vals):
                connector = req_vals["relationship"]["properties"][CONNECT_PROP]
                self._create_compose_connection(tpl.name, related_node, connector)
            elif "AttachesTo" in str(req_vals):
                connector = req_vals["relationship"]["properties"][ATTACH_PROP]
                self._create_compose_volume(tpl.name, related_node, connector)

    def _create_compose_image(self, node, image):
        """ Create an image entry in the compose data """
        # Add the image entry under the service key
        node = self.compose_data.setdefault("services", {}).setdefault(node, {})
        if "image" not in node:
            node["image"] = image

    def _create_compose_properties(self, key, entry):
        """ Create an image entry in the compose data """
        # Add properties under the service key
        self.compose_data.setdefault(key, {}).update(entry)

    def _create_compose_volume(self, node, volume, location):
        """ Create a volume entry in the compose data """
        # Add the entry under the volumes key
        volume_key = self.compose_data.setdefault("volumes", {})
        if volume not in volume_key:
            volume_key[volume] = {}

        # Add the entry for the volume under the current node
        node = self.compose_data["services"][node].setdefault("volumes",[])
        entry = "{}:{}".format(volume, location)
        if entry not in node:
            node.append(entry)

    def _create_compose_connection(self, node, target, network):
        """ Create a network entry in the compose data """
        # Add the entry under the networks key
        network_key = self.compose_data.setdefault("networks", {})
        if network not in network_key:
            network_key[network] = {"driver":"overlay"}

        # Add the entry for the network under the current node
        node = self.compose_data["services"][node].setdefault("networks",[])
        if network not in node:
            node.append(network)

        # Add the entry for the network under the target node
        target = self.compose_data["services"][target].setdefault("networks",[])
        if network not in target:
            target.append(network)

    def _create_compose_constraint(self, node, host):
        """ Create a constraint entry in the compose data """
        # Add the constraint under services key
        node = self.compose_data["services"][node].setdefault("deploy",{}) \
                                                  .setdefault("placement",{}) \
                                                  .setdefault("constraints",[])
        entry = "node.labels.host == {}".format(host)
        if entry not in node:
            node.append(entry)
