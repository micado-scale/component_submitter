from abstracts import container_orchestrator as abco
from abstracts.exceptions import AdaptorError, AdaptorCritical
import subprocess
import ruamel.yaml as yaml
import logging
import generator
DOCKER_THINGS = (DOCKER_CONTAINER, DOCKER_NETWORK, DOCKER_VOLUME) = \
                ("tosca.nodes.MiCADO.Container.Application.Docker",
                "tosca.nodes.MiCADO.network.Network.Docker",
                "tosca.nodes.MiCADO.Volume.Docker")
logger = logging.getLogger("adaptors."+__name__)

class DockerAdaptor(abco.ContainerAdaptor):

    def __init__(self):
        logger.debug("initialize the Docker Adaptor")
        super().__init__()
        self.compose_data = {"version":"3.4"}
        logger.info("Adaptor ready to be used")

    def translate(self, parsed):
        """ Translate the parsed subset to the Compose format """

        logger.info("Starting translation...")
        for tpl in parsed.nodetemplates:
            if DOCKER_CONTAINER in tpl.type:
                self._get_properties(tpl, "services")
                self._get_artifacts(tpl, parsed.repositories)

        if not self.compose_data.get("services"):
            logger.error("No TOSCA nodes of Docker type!")
            raise AdaptorCritical("No TOSCA nodes of Docker type!")

        for tpl in parsed.nodetemplates:
            if DOCKER_CONTAINER in tpl.type:
                self._get_requirements(tpl)
            elif DOCKER_NETWORK in tpl.type:
                self._get_properties(tpl, "networks")
            elif DOCKER_VOLUME in tpl.type:
                self._get_properties(tpl, "volumes")

    def execute(self):
        """ Execute the Compose file """
        logger.info("Starting Docker execution...")
        id_stack=generator.id_generator()
        self.dump_compose("docker-compose.yaml")
        try:
            subprocess.run(["docker", "stack", "deploy", "--compose-file",
                            "docker-compose.yaml", id_stack], check=True)
            #logger.info("subprocess.run([\"docker\", \"stack\", \"deploy\", \"--compose-file\", \"docker-compose.yaml\", id_stack], check=True)")
        except subprocess.CalledProcessError:
            logger.error("Cannot execute Docker")
            raise AdaptorCritical("Cannot execute Docker")
        logger.info("Docker running...")
        return id_stack

    def undeploy(self, id_stack):
        """ Undeploy this application """
        logger.info("Undeploying the application")
        try:
            subprocess.run(["docker", "stack", "down", id_stack], check=True)
        except subprocess.CalledProcessError:
            logger.error("Cannot undeploy the stack")
            raise AdaptorCritical("Cannot undeploy the stack")
        logger.info("Stack is down...")

    def dump_compose(self, path):
        """ Dump to Docker-Compose file """

        class NoAliasRTDumper(yaml.RoundTripDumper):
            """ Turn off aliases, preserve order """

            def ignore_aliases(self, data):
                return True

        with open(path, 'w') as file:
            yaml.dump(self.compose_data, file,
                      default_flow_style=False, Dumper=NoAliasRTDumper)

    def _get_properties(self, node, key):
        """ Get TOSCA properties """

        properties = node.get_properties()
        entry = {node.name: {}}

        for property in properties:
            try:
                entry[node.name][property] = node.get_property_value(property).result()
            except AttributeError as a:
                logger.debug("Error caught {}, trying without .result()".format(a))
                entry[node.name][property] = node.get_property_value(property)
        # Write the compose data
        self._create_compose_properties(key, entry)

    def _get_artifacts(self, tpl, repositories):
        """ Get TOSCA artifacts """

        image = tpl.entity_tpl.get("artifacts").get("image")
        # Get the repository, include in image name if not Docker Hub
        repository = image.get("repository")
        if repository and "docker_hub" not in repository:
            for repo in repositories:
                if repository == repo.name:
                    repository = repo.reposit
                    break
            else:
                raise AdaptorCritical("No repository: {}".format(repository))
        else:
            repository = ""

        image = image["file"]
        image = "{}{}".format(repository, image)

        # Write the compose data
        self._create_compose_image(tpl.name, image)

    def _get_requirements(self, tpl):
        """ Get TOSCA requirements """

        for requirement in tpl.requirements:
            req_vals = list(requirement.values())[0]
            related_node = req_vals["node"]

            # Fulfill the HostedOn relationship
            #DISABLE until fully implemented
            #if "HostedOn" in str(req_vals):
            #    self._create_compose_constraint(tpl.name, related_node)

            # Fulfill the ConnectsTo and AttachesTo relationships
            if "ConnectsTo" in str(req_vals):
                connector = req_vals["relationship"]["properties"]["network"]
                self._create_compose_connection(tpl.name, related_node, connector)
            elif "AttachesTo" in str(req_vals):
                connector = req_vals["relationship"]["properties"]["location"]
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
