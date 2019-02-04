import os
import subprocess
import logging
import shutil
import filecmp
import time

import kubernetes.client
import kubernetes.config
from toscaparser.tosca_template import ToscaTemplate

import utils
from abstracts import base_adaptor
from abstracts.exceptions import AdaptorCritical

logger = logging.getLogger("adaptors." + __name__)

TOSCA_TYPES = (DOCKER_CONTAINER, CONTAINER_VOLUME, 
               VOLUME_ATTACHMENT, KUBERNETES_INTERFACE) = \
              ("tosca.nodes.MiCADO.Container.Application.Docker", "tosca.nodes.MiCADO.Container.Volume", 
               "tosca.relationships.AttachesTo", "Kubernetes")

SWARM_PROPERTIES = ['expose']
POD_SPEC_FIELDS = ('activeDeadlineSeconds', 'affinity', 'automountServiceAccountToken', 'dnsConfig', 
                   'dnsPolicy', 'enableServiceLinks', 'hostAliases', 'hostIPC', 'hostNetwork', 'hostPID', 
                   'hostname', 'imagePullSecrets', 'initContainers', 'nodeName', 'nodeSelector', 'priority', 
                   'priorityClassName', 'readinessGates', 'restartPolicy', 'runtimeClassName', 'schedulerName', 
                   'securityContext', 'serviceAccount', 'serviceAccountName', 'shareProcessNamespace', 'subdomain', 
                   'terminationGracePeriodSeconds', 'tolerations', 'volumes')

class KubernetesAdaptor(base_adaptor.Adaptor):

    """ The Kubernetes Adaptor class

    Carry out a translation from a TOSCA ADT to a Kubernetes Manifest,
    and the subsequent execution, update and undeployment of the translation.
    
    """
    
    def __init__(self, adaptor_id, config, template=None):
        """ init method of the Adaptor """ 
        super().__init__()

        logger.debug("Initialising Kubernetes Adaptor class...")
        self.status = "Initialising..."

        if template and not isinstance(template, ToscaTemplate):
            raise AdaptorCritical("Template is not a valid TOSCAParser object")        

        self.ID = adaptor_id
        self.short_id = '_'.join(adaptor_id.split('_')[:-1])
        self.config = config
        self.tpl = template
        self.manifest_path = "{}{}.yaml".format(self.config['volume'], self.ID)
        self.manifest_tmp_path = "{}tmp_{}.yaml".format(self.config['volume'], self.ID)

        self.manifests = []
        self.services = []
        self.output = {}

        logger.info("Kubernetes Adaptor is ready.")
        self.status = "Initialised"

    def translate(self, update=False):
        """ Translate the relevant sections of the ADT into a Kubernetes Manifest """
        logger.info("Translating into Kubernetes Manifests")
        self.status = "Translating..."

        nodes = self.tpl.nodetemplates
        repositories = self.tpl.repositories
        
        for node in nodes:
            kube_interface = \
                [x for x in node.interfaces if KUBERNETES_INTERFACE in x.type]
            if DOCKER_CONTAINER in node.type and kube_interface:
                if '_' in node.name:
                    logger.error("ERROR: Use of underscores in {} workload name prohibited".format(node.name))
                    raise AdaptorCritical("ERROR: Use of underscores in {} workload name prohibited".format(node.name))
                interface = kube_interface[0]
                self._create_manifests(node, interface, repositories)

        if not self.manifests:
            logger.info("No nodes to orchestrate with Kubernetes. Do you need this adaptor?")
            self.status = "Skipped Translation"
            return

        if update:
            utils.dump_list_yaml(self.manifests, self.manifest_tmp_path)
        else:
            utils.dump_list_yaml(self.manifests, self.manifest_path)

        logger.info("Translation complete")
        self.status = "Translated"

    def execute(self, update=False):
        """ Execute """
        logger.info("Executing Kubernetes Manifests...")
        self.status = "Executing..."

        if not self.manifests:
            logger.info("No nodes to orchestrate with Kubernetes. Do you need this adaptor?")
            self.status = "Skipped Execution"
            return

        if update:
            operation = ['kubectl', 'apply', '-f', self.manifest_path]
        else:
            operation = ['kubectl', 'create', '-f', self.manifest_path, '--save-config']

        try:
            if self.config['dry_run']:
                logger.info("DRY-RUN: kubectl creates workloads...")
            else:
                logger.debug("Executing {}".format(operation))
                subprocess.run(operation, stderr=subprocess.PIPE, check=True)

        except subprocess.CalledProcessError:            
            logger.error("Cannot execute kubectl")
            raise AdaptorCritical("Cannot execute kubectl")

        logger.info("Kube objects deployed, trying to get outputs...")
        self._get_outputs()
        logger.info("Execution complete")
        self.status = "Executed"

    def update(self):
        """ Update """
        logger.info("Updating Kubernetes Manifests")
        last_status = self.status
        self.status = "Updating..."

        logger.debug("Creating tmp translation...")
        self.translate(True)
        
        if not self.manifests:
            logger.info("No nodes to orchestrate with Kubernetes. Do you need this adaptor?")
            self.status = "Skipped Update"
            return

        if filecmp.cmp(self.manifest_path, self.manifest_tmp_path):
            logger.debug("No update - removing {}".format(self.manifest_tmp_path))
            os.remove(self.manifest_tmp_path)
            logger.info("Nothing to update")
            self.status = last_status
        else:
            logger.debug("Updating - removing {}".format(self.manifest_path))
            os.rename(self.manifest_tmp_path, self.manifest_path)
            self.execute(True)
            logger.info("Update complete")
            self.status = "Updated"
    
    def undeploy(self):
        """ Undeploy """
        logger.info("Undeploying Kubernetes workloads")
        self.status = "Undeploying..."
        error = False
        
        # Try to delete workloads relying on hosted mounts first (WORKAROUND)
        operation = ["kubectl", "delete", "-f", self.manifest_path, "-l", "!hostedVol"]
        try:
            if self.config['dry_run']:
                logger.info("DRY-RUN: kubectl removes all workloads but hosted volumes...")
            else:
                logger.debug("Undeploy {}".format(operation))
                subprocess.run(operation, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError:
            logger.debug("Got error deleting non-hosted-mount workloads")
            error = True
        time.sleep(15)

        # Delete workloads hosting volumes
        operation = ["kubectl", "delete", "-f", self.manifest_path, "-l", "hostedVol"]
        try:
            if self.config['dry_run']:
                logger.info("DRY-RUN: kubectl removes remaining workloads...")
            else:
                logger.debug("Undeploy {}".format(operation))
                subprocess.run(operation, stderr=subprocess.PIPE, check=True)          
        except subprocess.CalledProcessError:
            logger.debug("Had some trouble removing hosted volume workload...")
            error = True

        if error:            
            raise AdaptorCritical("Had some trouble removing workloads!")
        logger.info("Undeployment complete")
        self.status = "Undeployed"

    def cleanup(self):
        """ Cleanup """
        logger.info("Cleaning-up...")
        self.status = "Cleaning-up..."

        try:
            os.remove(self.manifest_path)
        except OSError:
            logger.warning("Could not remove manifest file")

        try:
            if self.config['dry_run']:
                logger.info("DRY-RUN: cleaning up old manifests...")
            else:
                operation = ["docker", "exec", "occopus_redis", "redis-cli", "FLUSHALL"]
                subprocess.run(operation, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError:
            logger.warning("Could not flush occopus_redis")

        self.status = "Clean!"

    def query(self, query):
        """ Query """
        logger.info("Query ID {}".format(self.ID))
        kubernetes.config.load_kube_config()
        
        if query == 'nodes':
            client = kubernetes.client.CoreV1Api()
            return [x.metadata.to_dict() for x in client.list_node().items if not x.spec.taints]
        elif query == 'services':
            client = kubernetes.client.ExtensionsV1beta1Api()
            return [x.metadata.to_dict() for x in client.list_namespaced_deployment("default").items]

    def _get_outputs(self):
        """ Get outputs and their resultant attributes """
        logger.info("Fetching outputs...")

        def get_attribute(service, query):
            kubernetes.config.load_kube_config()
            if query == 'port':
                for svc in self.services:
                    if svc.get('node') == service:
                        name = svc.get('name')
                        namespace = svc.get('namespace')
                        client = kubernetes.client.CoreV1Api()
                        result = [x.to_dict() for x in client.read_namespaced_service(name, namespace).spec.ports]
                        self.output.setdefault(service, []).append(result)

        for output in self.tpl.outputs:
            node = output.value.get_referenced_node_template()
            if node.type == DOCKER_CONTAINER:
                service = node.name
                logger.debug("Inspect service: {}".format(service))
                query = output.value.attribute_name
                get_attribute(service, query)
            else:
                logger.warning("{} is not a Docker container!".format(node.name))
        
    def _create_manifests(self, node, interface, repositories):
        """ Create the manifest from the given node """
        implementation = interface.implementation
        inputs = interface.inputs
        properties = {key:val.value for key, val in node.get_properties().items()}

        resource = _get_resource(node, inputs, implementation, self.short_id)
        kind = resource.get('kind')
        resource_metadata = resource.get('metadata', {})
        resource_namespace = resource_metadata.get('namespace')
        resource_labels = resource_metadata.get('labels')

        self._get_service_manifests(node, properties, resource, inputs)

        # Get and set volume info
        volumes, volume_mounts = _get_volumes(node)
        if volumes:
            vol_list = inputs.setdefault('volumes', [])
            vol_list += volumes
        if volume_mounts:
            vol_list = properties.setdefault('volumeMounts', []) 
            vol_list += volume_mounts

        # Get container spec
        container = _get_container(node, properties, repositories, inputs)

        # Get pod metadata from container or resource
        pod_metadata = inputs.pop('metadata', {})
        pod_metadata.setdefault('labels', {'run': node.name})
        pod_labels = pod_metadata.get('labels')
        pod_metadata.setdefault('namespace', resource_namespace)

        # Separate data for pod.spec
        pod_data = _separate_data(POD_SPEC_FIELDS, inputs)

        # Cleanup metadata and inputs
        pod_metadata = {key:val for key, val in pod_metadata.items() if val}
        inputs = {key:val for key, val in inputs.items() if val}

        # Set pod spec and selector
        pod_spec = {'containers': [container], **pod_data}
        selector = {'matchLabels': pod_labels}  

        # Set template & pod spec
        if kind == 'Pod':
            spec = pod_spec
        elif kind == 'Job':
            template = {'spec': pod_spec}
            spec = {'template': template, **inputs}
        else:
            template = {'metadata': pod_metadata, 'spec': pod_spec}
            spec = {'selector': selector, 'template': template, **inputs}

        # Build manifests
        resource.setdefault('spec', spec)
        self.manifests.append(resource)

        return

    def _get_service_manifests(self, node, properties, resource, inputs):
        """ Build a service based on the provided port spec and template """
        # Find ports/clusterIP for service creation
        ports = _get_service_info(properties, node.name)
        services_to_build = {}
        service_types = ['clusterip', 'nodeport', 'LoadBalancer', 'ExternalIP']
        

        for port in ports:
            metadata = port.pop("metadata", {})
            service_name = metadata.get("name")
            port_type = port.pop("type", None)
            cluster_ip = port.pop("clusterIP", None)
            if not service_name:
                service_name = '{}-{}'.format(node.name, port_type.lower())
            service_entry = services_to_build.setdefault(service_name, {})

            service_entry.setdefault('type', port_type)
            service_entry.setdefault('metadata', metadata)
            service_entry.setdefault('clusterIP', cluster_ip)
            service_entry.setdefault('ports', []).append(port)
        
        if node.name not in services_to_build.keys():
            for s_type in service_types:
                entry = services_to_build.pop('{}-{}'.format(node.name, s_type), None)
                if entry:
                    services_to_build.setdefault(node.name, entry)
                    break

        for name, service in services_to_build.items():
            manifest, service_info = \
                _build_service(name, service, resource, node.name, inputs)
            if not manifest:
                continue
            self.manifests.append(manifest)
            self.services.append(service_info)    

def _get_api(kind):
    """ Return the apiVersion according to kind """
    # supported workloads & their api versions
    api_versions = {'DaemonSet': 'apps/v1', 'Deployment': 'apps/v1', 'Job': 'batch/v1', 
                    'Pod': 'v1', 'ReplicaSet': 'apps/v1', 'StatefulSet':'apps/v1',
                    'Ingress': 'extensions/v1beta1', 'Service': 'v1',
                    'PersistentVolumeClaim': 'v1', 'Volume': 'v1',
                    'Namespace': 'v1'}

    for resource, api in api_versions.items():
        if kind.lower() == resource.lower():
            return api
    
    logger.warning("Unknown kind: {}. Not supported...".format(kind))
    return 'unknown'

def _get_resource(node, inputs, implementation, short_id):
    """ Build and return the basic data for the workload """
    # kind
    if isinstance(implementation, str):
        kind = implementation
        implementation = {}
    kind = implementation.get('kind', 'Deployment')

    # apiVersion and name
    api_version = implementation.get('apiVersion', inputs.get('apiVersion', _get_api(kind)))
    name = implementation.get('name', node.name)

    # labels and metadata
    labels = implementation.get('labels', {})
    metadata = implementation.get('metadata', {'name': name, 'labels': labels})
    metadata.setdefault('labels', {}).setdefault('app', short_id)
    
    resource = {'apiVersion': api_version, 'kind': kind, 'metadata': metadata}

    return resource

def _build_service(service_name, service, resource, node_name, inputs):
    """ Build service and return a manifest """
    # Check for ports
    ports = service.get('ports')
    if not ports:
        logger.warning('No ports in service {}. Will not be created'.format(service_name))
        return None, None

    # Get resource metadata
    metadata = resource.get('metadata', {})
    resource_namespace = metadata.get('namespace')
    resource_labels = metadata.get('labels')

    # Get container metadata
    metadata = inputs.get('metadata', {})
    pod_labels = metadata.get('labels', {'run': node.name})

    # Set service metadata
    metadata = service.get('metadata', {})
    metadata.setdefault('name', service_name)
    metadata.setdefault('namespace', resource_namespace)
    metadata.setdefault('labels', resource_labels)
    
    # Set service info for outputs
    namespace = metadata.get('namespace', 'default')
    service_info = {'node': node_name, 'name': service_name, 'namespace': namespace}

    # Cleanup metadata
    metadata =  {key:val for key, val in metadata.items() if val}

    # Set type, clusterIP, ports
    port_type = service.get('type')
    cluster_ip = service.get('clusterIP')
    spec_ports = []
    for port in ports:
        spec_ports.append(port)

    # Set spec
    spec = {'ports': spec_ports, 'selector': pod_labels}
    if port_type != 'ClusterIP':
        spec.setdefault('type', port_type)
    if cluster_ip:
        spec.setdefault('clusterIP', cluster_ip)

    manifest = {'apiVersion': 'v1', 'kind': 'Service',
                'metadata': metadata, 'spec': spec}

    return manifest, service_info

def _get_container(node, properties, repositories, inputs):
    """ Return container spec """        

    # Get image
    image = _get_image(node.entity_tpl, repositories)
    if not image:
        raise AdaptorCritical("No image specified for {}!".format(node.name))
    properties.setdefault('image', image)

    # Remove any known swarm-only keys
    for key in SWARM_PROPERTIES:
        if properties.pop(key, None):
            logger.warning('Removed Swarm-option {}'.format(key))

    # Translate common properties
    properties.setdefault('name', properties.pop('container_name', node.name))
    properties.setdefault('command', properties.pop('entrypoint', '').split())
    properties.setdefault('args', properties.pop('cmd', '').split())
    docker_env = properties.pop('environment', {})
    env = []
    for key, value in docker_env:
        env.append({'name': key, 'value': value})
    properties.setdefault('env', env)
    
    # Translate other properties
    inputs.setdefault('terminationGracePeriodSeconds', properties.pop('stop_grace_period', None))
    docker_priv = properties.pop('privileged', None)
    if docker_priv:
        properties.setdefault('securityContext', {}).setdefault('privileged')
    properties.setdefault('stdin', properties.pop('stdin_open', None))
    properties.setdefault('livenessProbe', properties.pop('healthcheck', None))

    return {key:val for key, val in properties.items() if val}

def _separate_data(key_names, container):
    """ Separate workload specific data from the container spec """
    data = {}
    for x in key_names:
            try:
                data[x] = container.pop(x)
            except KeyError:
                pass
    return data

def _get_image(node, repositories):
    """ Return the full path to the Docker container image """
    details = node.get('artifacts', {}).get('image', {})
    image = details.get('file')
    repo = details.get('repository')
    if not image or not repo or not repositories:
        logger.warning("Missing top-level repository or file/repository in artifact - no image!")
        return ''

    if repo.lower().replace(' ','').replace('-','').replace('_','') != 'dockerhub':
        path = [x.reposit for x in repositories if x.name == repo]
        if path:
            image = '/'.join([path[0].strip('/'), image])
    
    return image

def _get_volumes(node):
    """ Return the volume spec for the workload """
    related = node.related_nodes
    requirements = node.requirements
    volumes = []
    volume_mounts = []

    for node in related:
        volume_mount_list = []

        kube_interface = \
            [x for x in node.interfaces if KUBERNETES_INTERFACE in x.type]
        if node.type == CONTAINER_VOLUME and kube_interface:
            inputs = kube_interface[0].inputs
            name = inputs.pop('name', node.name)
            volume_spec = {'name': name, **inputs}
        else:
            continue

        for requirement in requirements:
            volume = requirement.get('volume',{})
            relationship = volume.get('relationship', {}).get('type')
            path = volume.get('relationship', {}).get('properties', {}).get('location')
            if path and relationship == VOLUME_ATTACHMENT:
                if volume.get('node') == node.name:
                    volume_mount_spec = {'name': name, 'mountPath': path}
                    volume_mount_list.append(volume_mount_spec)
        
        if volume_mount_list:         
            volumes.append(volume_spec)
            volume_mounts += volume_mount_list

    return volumes, volume_mounts
    
def _get_service_info(properties, node_name):
    """ Return the info for creating a service """
    port_list = []
    # Get ports info
    ports = properties.pop('ports', None)
    if ports:
        for port in ports:
            container_port = port.get("containerPort")
            if container_port:
                properties.setdefault('ports', []).append(port)
                continue
            
            port_spec = _build_port_spec(port, node_name)
            if port_spec:
                port_list.append(port_spec)
    return port_list

def _build_port_spec(port, node_name):
    """ Return port spec """
    # Check if we have a port    
    target = port.get("targetPort", port.get("target"))
    publish = int(port.get("port", port.get("published", target)))
    if not publish and not target:
        logger.warning("No port in ports of {}".format(node_name))
        return
    if isinstance(target, str) and target.isdigit():
        target = int(target)

    # Check for a clusterIP
    cluster_ip = port.get('clusterIP')
    if cluster_ip:
        ip_split = cluster_ip.split('.')
        # Check if the ip is within range (kind of)
        if ip_split[0] == '10' and 96 <= int(ip_split[1]) <= 111:
            cluster_ip = cluster_ip
        elif ip_split[0] == 'None':     
            cluster_ip = 'None'           
        else:
            logger.warning("ClusterIP out of range 10.96.x.x - 10.111.x.x Kubernetes will assign one")

    # Assign protocol, name, type, metadata
    protocol = port.get("protocol", "TCP").upper()
    name = port.get('name', '{}-{}'.format(target, protocol.lower()))
    port_type = port.get('type', port.get('mode'))    
    metadata = port.get("metadata")

    # Assign node port if valid
    node_port = port.get('nodePort')
    if node_port:
        port_type = port_type or 'NodePort'
        if 30000 > int(node_port) > 32767:
            node_port = None
            logger.warning("nodePort out of range 30000-32767... Kubernetes will assign one")

    # Determine type if Swarm-style or empty
    if port_type == 'host':
        port_type = 'NodePort'
    elif port_type == 'ingress' or not port_type:
        port_type = 'ClusterIP'

    # Build a port spec
    port_spec = {"name": name,
                 "targetPort": target,
                 "port": publish,
                 "protocol": protocol,
                 "type": port_type,
                 "nodePort": node_port,
                 "metadata": metadata,
                 "clusterIP": cluster_ip}
    port_spec = {key:val for key, val in port_spec.items() if val}

    return port_spec