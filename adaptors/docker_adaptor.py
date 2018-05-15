"""
MiCADO Submitter Engine Docker Adaptor
--------------------------------------

A TOSCA to Docker (Swarm) adaptor.
"""

import subprocess
import os
import json
import filecmp
import logging

from toscaparser.tosca_template import ToscaTemplate

import utils
from abstracts import container_orchestrator as abco
from abstracts.exceptions import AdaptorCritical

logger = logging.getLogger("adaptors."+__name__)

#Some hard-coded TOSCA types that are relevant to Docker in this
#implementation of MiCADO
DOCKER_THINGS = (DOCKER_CONTAINER, DOCKER_NETWORK, DOCKER_VOLUME, DOCKER_IMAGE,
                 CONNECT_PROP, ATTACH_PROP) = \
                ("tosca.nodes.MiCADO.Container.Application.Docker",
                 "tosca.nodes.MiCADO.network.Network.Docker",
                 "tosca.nodes.MiCADO.Volume.Docker",
                 "tosca.artifacts.Deployment.Image.Container.Docker",
                 "network", "location")

COMPOSE_VERSION = "3.4"

class DockerAdaptor(abco.ContainerAdaptor):

    """ The Docker adaptor class

    Carries out the deployment of a Dockerised application or application stack
    based on a description of an application provided by a YAML file which
    follows the OpenStack TOSCA language specification.

    Implements abstract methods ``__init__()``, ``translate()``, ``execute()``,
    ``undeploy()`` and ``cleanup()``. Accepts as parameters an **adaptor_id**
    (required) and a **template** (optional). The ``translate()`` and ``update()``
    methods require both an **adaptor_id** and **template**. The ``execute()``,
    ``undeploy()`` and ``cleanup()`` methods require only the **adaptor_id** .

    :param string adaptor_id: The generated ID of the current application stack
    :param template: The ADT / ToscaTemplate of the current application stack
    :type template: ToscaTemplate <toscaparser.tosca_template.ToscaTemplate>

    Usage:
        >>> from docker_adaptor import DockerAdaptor
        >>> container_adapt = DockerAdaptor(<adaptor_id>, <ToscaTemplate>)
        >>> container_adapt.translate()
            (writes compose file to file/output_configs/<adaptor_id>.yaml)
        >>> container_adapt.execute()
            (stack deployed)
        >>> container_adapt.update()
            (stack update if template is changed, otherwise nothing)
        >>> container_adapt.undeploy()
            (stack undeployed)
        >>> container_adapt.cleanup()
            (compose file removed from file/output_configs/)


    """

    def __init__(self, adaptor_id, template=None):
        """ Constructor method of the Adaptor as described above """
        super().__init__()
        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")

        logger.debug("Initialising the Docker adaptor with ID & TPL...")
        self.compose_data = {}
        self.ID = adaptor_id
        self.tpl = template
        self.output = dict()
        logger.info("DockerAdaptor ready to go!")

    def translate(self, tmp=False):
        """ Translate the self.tpl subset to the Compose format

        Does the work of mapping the Docker relevant sections of TOSCA into a
        dictionary following the Docker-Compose format, then dumping output to
        a .yaml file in output_configs/

        :param bool tmp: Set ``True`` for update() - outputfile gets prefix ``tmp_``

        :raises: AdaptorCritical
        """

        logger.info("Starting translation to compose...")
        self.compose_data = {"version": COMPOSE_VERSION}

        for node in self.tpl.nodetemplates:
            if DOCKER_CONTAINER in node.type:
                self._compose_properties(node, "services")
                self._compose_artifacts(node, self.tpl.repositories)
                self._compose_requirements(node)
            elif DOCKER_NETWORK in node.type:
                self._compose_properties(node, "networks")
            elif DOCKER_VOLUME in node.type:
                self._compose_properties(node, "volumes")

        if not self.compose_data.get("services"):
            logger.error("No TOSCA nodes of Docker type!")
            raise AdaptorCritical("No TOSCA nodes of Docker type!")

        if tmp is False:
            utils.dump_order_yaml(
                self.compose_data, f'files/output_configs/{self.ID}.yaml')
        else:
            utils.dump_order_yaml(
                self.compose_data, f'files/output_configs/tmp_{self.ID}.yaml')


    def execute(self):
        """ Deploy the stack onto the Swarm

        Executes the ``docker stack deploy`` command on the Docker-Compose file
        which was created in ``translate()``

        :raises: AdaptorCritical
        """
        logger.info("Starting Docker execution...")

        # Dry runs in comments (no Docker in our test env)
        try:
            #subprocess.run(["docker", "stack", "deploy", "--compose-file",
            #f'files/output_configs/{self.ID}.yaml', self.ID[:8]], check=True)
            logger.info(f'subprocess.run([\"docker\", \"stack\", \"deploy\", '
                        f'\"--compose-file\", \"docker-compose.yaml\", '
                        f'{self.ID[:8]}], check=True)')
        except subprocess.CalledProcessError:
            logger.error("Cannot execute Docker")
            raise AdaptorCritical("Cannot execute Docker")
        logger.info("Docker running, trying to get outputs...")
        self._get_outputs()

    def undeploy(self):
        """ Undeploy the stack from Docker

        Runs ``docker stack down`` using the given ID to bring down the stack.

        :raises: AdaptorCritical
        """
        logger.info("Undeploying the application")

        try:
            #subprocess.run(["docker", "stack", "down", self.ID[:8]], check=True)
            logger.debug(f'Undeploy application with ID: {self.ID}')
        except subprocess.CalledProcessError:
            logger.error("Cannot undeploy the stack")
            raise AdaptorCritical("Cannot undeploy the stack")
        logger.info("Stack is down...")

    def cleanup(self):
        """ Remove the associated Compose file

        Removes output file created for this stack from ``files/output_configs/``

        .. note::
          A warning will be logged if the Compose file cannot be removed
        """
        logger.info(f'Cleanup config for ID {self.ID}')
        try:
            os.remove(f'files/output_configs/{self.ID}.yaml')
        except OSError as e:
            logger.warning(e)

    def update(self):
        """ Update an already deployed application stack with a changed ADT

        Translates the template into a ``tmp`` compose file, differentiates ``tmp``
        with the current compose file. If different, replace current compose with
        ``tmp`` compose, and call execute().
        """
        logger.info("Starting the update...")
        logger.debug("Creating temporary template...")
        self.translate(True)

        if not self._differentiate():
            logger.debug("tmp file different, replacing old config and executing")
            os.rename(f'files/output_configs/tmp_{self.ID}.yaml',
                      f'files/output_configs/{self.ID}.yaml')
            self.execute()
        else:
            try:
                logger.debug("tmp file is the same, removing the tmp file")
                os.remove(f'files/output_configs/tmp_{self.ID}.yaml')
            except OSError as e:
                logger.warning(e)

    def _get_outputs(self):
        """ Get outputs and their resultant attributes """
        def get_attribute(service, query):
            """ Get attribute from a service """
            try:
            #    inspect = subprocess.check_output(
            #                        ["docker", "service", "inspect", service] )
            #    [inspect] = json.loads(inspect.decode('UTF-8'))
                inspect = {"Endpoint": {"VirtualIPs": "120.12.12.12", "Ports":"120"}}
            except (subprocess.CalledProcessError, TypeError):
                logger.warning(f'Cannot inspect the service {service}')
            else:
                if query == "ip_address":
                    result = inspect.get("Endpoint").get("VirtualIPs")
                elif query == "port":
                    result = inspect.get("Endpoint").get("Ports")

                logger.info(f'[OUTPUT] Service: <{service}> Attr: <{query}>\n'
                            f'    RESULT: {result}')
                self.output.update({query:{"service": service, "result": result}})

        for output in self.tpl.outputs:
            node = output.value.get_referenced_node_template()
            if node.type == DOCKER_CONTAINER:
                service = f'{self.ID[:8]}_{node.name}'
                logger.debug(f'Inspect service: {service}')
                query = output.value.attribute_name
                get_attribute(service, query)
            else:
                logger.warning(f'{node.name} is not a Docker container!')

    def _differentiate(self):
        """ Compare two compose files """
        return filecmp.cmp(f'files/output_configs/{self.ID}.yaml',
                           f'files/output_configs/tmp_{self.ID}.yaml')

    def _compose_properties(self, node, key):
        """ Get TOSCA properties, write compose entries """
        properties = node.get_properties()
        entry = {}

        for prop in properties:
            try:
                entry[prop] = node.get_property_value(prop).result()
            except AttributeError as e:
                logger.debug(f'Error caught {e}, trying without .result()')
                entry[prop] = node.get_property_value(prop)

        # Write the compose data
        self.compose_data.setdefault(key, {}).setdefault(node.name, {}).update(entry)

    def _compose_artifacts(self, node, repositories):
        """ Get TOSCA artifacts, write compose entry"""
        try:
            artifacts = node.entity_tpl.get("artifacts").values()
        except AttributeError:
            raise AdaptorCritical("No artifacts found!")

        for artifact in artifacts:
            if DOCKER_IMAGE in artifact.get("type"):
                break
        else:
            raise AdaptorCritical(f'No artifact of type <{DOCKER_IMAGE}>')

        repository = artifact.get("repository")
        if repository and "docker_hub" not in repository:
            for repo in repositories:
                if repository == repo.name:
                    repository = repo.reposit
                    break
        else:
            repository = ""

        image = f'{repository}{artifact["file"]}'

        # Write the compose data
        node = self.compose_data.setdefault("services", {}).setdefault(node.name, {})
        node["image"] = image

    def _compose_requirements(self, node):
        """ Get TOSCA requirements, write compose entries """
        for requirement in node.requirements:
            req_vals = list(requirement.values())[0]
            related_node = req_vals["node"]

            #disable HostedOn until fully implemented
            if "HostedOn" in str(req_vals):
                #self._create_compose_constraint(node.name, related_node)
                pass

            elif "ConnectsTo" in str(req_vals):
                connector = req_vals["relationship"]["properties"][CONNECT_PROP]
                self._create_compose_connection(node.name, related_node, connector)

            elif "AttachesTo" in str(req_vals):
                connector = req_vals["relationship"]["properties"][ATTACH_PROP]
                self._create_compose_volume(node.name, related_node, connector)

    def _create_compose_volume(self, node, volume, location):
        """ Create a volume entry in the compose data under volumes """
        volume_key = self.compose_data.setdefault("volumes", {})
        volume_key.update({volume: {}})

        # Add the entry for the volume under the current node's key in compose
        node = self.compose_data.setdefault("services", {}) \
                                .setdefault(node, {}).setdefault("volumes", [])
        entry = f'{volume}:{location}'
        if entry not in node:
            node.append(entry)

    def _create_compose_connection(self, node, target, network):
        """ Create a network entry in the compose data under networks """
        network_key = self.compose_data.setdefault("networks", {})
        network_key.update({network: {"driver":"overlay"}})

        # Add the entry for the network under the current node's key in compose
        node = self.compose_data.setdefault("services", {}) \
                                .setdefault(node, {}).setdefault("networks", [])
        if network not in node:
            node.append(network)

        # Add the entry for the network under the target node's key in compose
        target = self.compose_data.setdefault("services", {}) \
                                  .setdefault(target, {}).setdefault("networks", [])
        if network not in target:
            target.append(network)

    def _create_compose_constraint(self, node, host):
        """ Create a constraint entry in the compose data """
        # Add the constraint under services key for the relevant node
        node = self.compose_data.setdefault("services", {}).setdefault(node, {}) \
                                .setdefault("deploy", {}) \
                                .setdefault("placement", {}) \
                                .setdefault("constraints", [])
        entry = f'node.labels.host == {host}'
        if entry not in node:
            node.append(entry)
