from abstracts import container_orchestrator as abco
from abstracts.exceptions import AdaptorError, AdaptorCritical, AdaptorWarning
import ruamel.yaml as yaml
import logging
DOCKER_THINGS = (DOCKER_CONTAINER, DOCKER_IMAGE, DOCKER_REPO,
                 DOCKER_NETWORK, DOCKER_VOLUME) = \
                ("tosca.nodes.MiCADO.Container.Application.Docker",
                "tosca.artifacts.Deployment.Image.Container.Docker",
                "docker_hub","tosca.nodes.MiCADO.network.Network.Docker",
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
            logger.warning("No TOSCA nodes of Docker type!")
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
        logger.info("Starting execution...")

        self.dump_compose("docker-compose.yaml")

    def undeploy(self):
        """ Undeploy this application """
        logger.info("Undeploying the application")
        # TODO: create the mechanism of undeploy

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
                logger.debug("error caught {}, then not getting the result".format(a))
                entry[node.name][property] = node.get_property_value(property)
        # Write the compose data
        self._create_compose_properties(key, entry)

    def _get_artifacts(self, tpl, repositories):
        """ Get TOSCA artifacts """

        artifacts = tpl.entity_tpl.get("artifacts")

        # Get the repository, include in image name if not Docker Hub
        repository = artifacts["image"].get("repository")
        if repository and "docker_hub" not in repository:
            for repo in repositories:
                if repository == repo.name:
                    repository = repo.reposit
                    break
            else:
                raise AdaptorCritical("No repository: {}".format(repository))
        else:
            repository = ""

        image = artifacts["image"]["file"]
        image = "{}{}".format(repository, image)

        # Write the compose data
        self._create_compose_image(tpl.name, image)

    def _get_requirements(self, tpl):
        """ Get TOSCA requirements """

        for requirement in tpl.requirements:

            # Fulfill the HostedOn relationship
            if "host" in requirement.keys():
                host = requirement["host"]["node"]
                self._create_compose_constraint(tpl.name, host)

            # Fulfill the ConnectsTo relationship
            elif "service" in requirement.keys():
                target = requirement["service"]["node"]
                network = requirement["service"]["relationship"] \
                                     ["properties"]["target"]
                self._create_compose_connection(tpl.name, target, network)

            # Fulfill the AttachesTo relationship
            elif "volume" in requirement.keys():
                volume = requirement["volume"]["node"]
                location = requirement["volume"]["relationship"] \
                                      ["properties"]["target"]
                self._create_compose_volume(tpl.name, volume, location)

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
