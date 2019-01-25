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
                kind = kube_interface[0].implementation or 'Deployment'
                inputs = kube_interface[0].inputs
                self._create_manifests(node, inputs, kind, repositories)

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
        mountflag = False
        
        # Try to delete workloads with mounted volumes first (WORKAROUND)
        operation = ["kubectl", "delete", "all", "-l", "volmount=flag"]
        try:
            if self.config['dry_run']:
                logger.info("DRY-RUN: kubectl removes mounts...")
            else:
                logger.debug("Undeploy mounts {}".format(operation))
                subprocess.run(operation, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError:
            logger.debug("Found no mounted vols to remove first...")
        else:
            logger.info("Some workloads with mounted vols were removed first...")
            mountflag = True
            time.sleep(15)

        # Normal deletion of workloads
        operation = ["kubectl", "delete", "-f", self.manifest_path]
        try:
            if self.config['dry_run']:
                logger.info("DRY-RUN: kubectl removes workloads...")
            else:
                logger.debug("Undeploy {}".format(operation))
                subprocess.run(operation, stderr=subprocess.PIPE, check=True)          
        except subprocess.CalledProcessError:
            if not mountflag:
                logger.debug("Had some trouble removing workloads...")
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
        
    def _create_manifests(self, node, inputs, kind, repositories):
        """ Create the manifest from the given node """

        # Set apiVersion and metadata
        api_version = inputs.get('apiVersion', _get_api(kind))
        labels = {'app': self.short_id}
        metadata = {'name': node.name, 'labels': labels}

        # Get volume info
        volumes, volume_mounts = _get_volumes(node.related_nodes, node.requirements)
        if volumes:
            vol_list = inputs.setdefault('volumes', [])
            vol_list += volumes
        if volume_mounts:
            vol_list = inputs.setdefault('volumeMounts', []) 
            vol_list += volume_mounts
        
        # Set container spec
        container_name = inputs.get('name', '{}-container'.format(node.name))
        image = _get_image(node.entity_tpl, repositories) or inputs.get('image')
        if not image:
            raise AdaptorCritical("No image specified for {}!".format(node.name))
        container = {'name': container_name, 'image': image, **inputs}

        # Separate data for pod/job/deloyment/daemonset-statefulset
        pod_keys = ['metadata','tolerations','volumes','terminationGracePeriodSeconds',
                     'restartPolicy']     
        pod_data = _separate_data(pod_keys, container)

        job_keys = ['activeDeadlineSeconds', 'backoffLimit', 'ttlSecondsAfterFinished',
                    'parallelism', 'completions']
        job_data = _separate_data(job_keys, container)
        
        deploy_keys = ['strategy']
        deploy_data = _separate_data(deploy_keys, container)

        update_keys = ['updateStrategy']
        update_data = _separate_data(update_keys, container)

        # Set pod metadata, namespace and spec
        pod_metadata = pod_data.pop('metadata', metadata)
        pod_metadata.setdefault('labels', {}).setdefault('app', self.short_id)
        namespace = pod_metadata.get('namespace')
        if namespace:
            metadata['namespace'] = namespace
        pod_spec = {'containers': [container], **pod_data}

        # Set pod labels and selector
        pod_labels = pod_metadata.get('labels', {'app': self.short_id})
        selector = {'matchLabels': pod_labels}

        # Find top level ports/clusterIP for service creation
        ports = _get_ports(node.get_properties_objects(), node.name)
        if ports:
            idx = 0
            cluster_ip = [x for x in ports if x.get('clusterIP')]
            if cluster_ip:
                cluster_ip = cluster_ip[0].get('clusterIP')

            # Create a different service for each type
            for port_type in ['ClusterIP', 'NodePort', 'LoadBalancer', 'ExternalName']:
                same_ports = [x for x in ports if x.get('type') == port_type]
                service_name = node.name
                if idx:
                    service_name += "-{}".format(port_type.lower())
                if same_ports:
                    self._build_service(same_ports, port_type, pod_labels, service_name, 
                                        cluster_ip, namespace, node.name, metadata.get('labels'))
                    idx += 1

        # Set template & pod spec
        if kind == 'Pod':
            metadata = pod_metadata
            spec = pod_spec
        elif kind == 'Job':
            template = {'spec': pod_spec}
            spec = {'template': template, **job_data}
        else:
            template = {'metadata': pod_metadata, 'spec': pod_spec}
            spec = {'selector': selector, 'template': template}

        # Set specific spec info for Deployments, StatefulSets and DaemonSets
        if kind == 'Deployment' and deploy_data:
            spec.update(deploy_data)
        elif (kind == 'StatefulSet' or kind == 'DaemonSet') and update_data:
            spec.update(update_data)

        # Set volume mounted flag
        if volume_mounts:
            metadata.setdefault('labels', {}).setdefault('volmount', 'flag')

        # Build manifests
        manifest = {'apiVersion': api_version, 'kind': kind, 
                    'metadata': metadata, 'spec': spec}
        self.manifests.append(manifest)

        return

    def _build_service(self, ports, port_type, selector, service_name, cluster_ip, namespace, node_name, meta_labels):
        """ Build a service based on the provided port spec and template """
        
        # Set metadata and type        
        metadata = {'name': service_name, 'labels': meta_labels}      
        if namespace:
            metadata['namespace'] = namespace
        else:
            namespace = 'default'
        
        # Set service info for outputs
        service_info = {'node': node_name, 'name': service_name, 'namespace': namespace}
        self.services.append(service_info)
        
        # Set ports
        spec_ports = []
        for port in ports:
            port.pop('type', None)
            spec_ports.append(port)

        # Set spec
        spec = {'ports': spec_ports, 'selector': selector}
        if port_type != 'ClusterIP':
            spec.setdefault('type', port_type)
        if cluster_ip:
            spec.setdefault('clusterIP', cluster_ip)

        manifest = {'apiVersion': 'v1', 'kind': 'Service',
                    'metadata': metadata, 'spec': spec}
        self.manifests.append(manifest)

        return

def _get_api(kind):
    """ Return the apiVersion according to kind """
    # List supported workloads & their api versions
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

def _get_volumes(related, requirements):
    """ Return the volume spec for the workload """
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
    
def _get_ports(properties, node_name):
    """ Return the port spec for the container """
    port_list = []
    for prop in properties:
        
        # Gets assigned cluster IP
        if prop.name == "clusterIP" or prop.name == 'ip':
            cluster_ip = prop.value.split('.')
            # Check if the ip is within range (kind of)
            if cluster_ip[0] == '10' and 96 <= int(cluster_ip[1]) <= 111:
                port_list.append({'clusterIP': prop.value})
            elif cluster_ip[0] == 'None':                
                port_list.append({'clusterIP': 'None'})                
            else:
                logger.warning("ClusterIP out of range 10.96.x.x - 10.111.x.x Kubernetes will assign one")

        # Gets port info
        elif prop.name == "ports":
            for port in prop.value:
                # Check if we have a valid target port
                target = port.get("target", port.get("targetPort", port.get("port")))
                if not target:
                    logger.warning("Bad port spec in properties of {}".format(node_name))
                    break

                # Build a port spec
                port_spec = {"targetPort": int(target),                                
                             "port": int(port.get("source", port.get("port", target))),
                             "protocol": port.get("protocol", "TCP").upper()}     
                
                # Assign node port if valid
                node_port = port.get('nodePort')
                if node_port:
                    node_port = int(node_port)
                    port_spec.setdefault('type', 'NodePort')
                    if 30000 <= node_port <= 32767:
                        port_spec.setdefault('nodePort', node_port)
                    else:
                        logger.warning("nodePort out of range 30000-32767... Kubernetes will assign one")                            

                # Assign name
                name = port.get('name', '{}-{}'.format(target, port_spec['protocol'].lower()))
                port_spec.setdefault('name', name)

                # Assign type
                port_type = port.get('type', port.get('mode'))
                if port_type:
                    port_spec.update({'type': port_type})
                else:
                    port_spec.setdefault('type', 'ClusterIP')               

                port_list.append(port_spec)
    return port_list