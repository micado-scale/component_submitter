#!/usr/bin/python
CAPABILITIES = (NUM_CPUS, DISK_SIZE, MEM_SIZE, PROJECT_ID, USER_DOMAIN_NAME,
             IMAGE_ID, NETWORK_ID, FLAVOR_NAME, SERVER_NAME, KEY_NAME, SECURITY_GROUPS, FLOATING_IP,
				FLOATING_IP_POOL) = \
    ('num_cpus', 'disk_size', 'mem_size', 'project_id', 'user_domain_name',
     'image_id', 'network_id', 'flavor_name', 'server_name', 'key_name', 'security_groups', 'floating_ip',
	 'floating_ip_pool')

ENDPOINT = 'endpoint_cloud'
import yaml
class Nova():

    def __init__(self, node):
        capabilities = node.get_capability("host")

        self._set_endpoint(node.get_property_value("cloud")[ENDPOINT])
        for n in  CAPABILITIES:
			self._set_params(n,capabilities.get_property_value(n))

    def _set_params(self, param, value):
        if param is NUM_CPUS:
            self._set_num_cpus(value)
        elif param is DISK_SIZE:
            self._set_disk_size(value)
        elif param is MEM_SIZE:
            self._set_mem_size(value)
        elif param is PROJECT_ID:
            self._set_project_id(value)
        elif param is USER_DOMAIN_NAME:
            self._set_user_domain_name(value)
        elif param is IMAGE_ID:
            self._set_image_id(value)
        elif param is NETWORK_ID:
            self._set_network_id(value)
        elif param is FLAVOR_NAME:
            self._set_flavor_name(value)
        elif param is SERVER_NAME:
			self._set_server_name(value)
        elif param is KEY_NAME:
            self._set_key_name(value)
        elif param is SECURITY_GROUPS:
            self._set_security_groups(value)
        elif param is FLOATING_IP:
            self._set_floating_ip(value)
        elif param is FLOATING_IP_POOL:
            self._set_floating_ip_pool(value)
        else:
            raise BaseException("param not related to Nova")

    def _set_num_cpus(self, num_cpus):
        self.num_cpus = num_cpus
    def _set_disk_size(self, disk_size):
        self.disk_size = disk_size
    def _set_mem_size(self, mem_size):
        self.mem_size = mem_size
    def _set_project_id(self, project_id):
        self.project_id = project_id
    def _set_user_domain_name(self, domain_name):
        self.domain_name = domain_name
    def _set_image_id(self, image_id):
        self.image_id = image_id
    def _set_network_id(self, network_id):
        self.network_id = network_id
    def _set_flavor_name(self, flavor_name):
        self.flavor_name = flavor_name
    def _set_server_name(self, server_name):
        self.server_name = server_name
    def _set_endpoint(self, endpoint):
        self.endpoint = endpoint
    def _set_key_name(self, key_name):
        self.key_name = key_name
    def _set_security_groups(self, security_groups):
        self.security_groups = security_groups
    def _set_floating_ip(self, floating_ip):
        self.floating_ip = floating_ip
    def _set_floating_ip_pool(self, floating_ip_pool):
        self.floating_ip_pool = floating_ip_pool

    def get_num_cpu(self):
        return self.num_cpus
    def get_disk_size(self):
        return self.disk_size
    def get_mem_size(self):
        return self.get_mem_size()
    def get_libdrive_id(self):
        return self.libdrive_id
    def get_vcn_password(self):
        return self.vcn_password
    def get_host_name(self):
        return self.host_name
    def get_publish_key_id(self):
        return self.publish_key_id
    def get_firewall_policy(self):
        return self.firewall_policy
    def get_description(self):
        return self.description
    def get_endpoint(self):
        return self.get_endpoint()

    def file(self):
        resource = dict()
        resource.update(type="nova",endpoint=self.endpoint, project_id=self.project_id,
                        user_domain_name=self.domain_name, image_id=self.image_id, network_id=self.network_id,
                        flavor_name=self.flavor_name, key_name=self.key_name, security_groups=self.security_groups,
                        floating_ip=self.floating_ip, floating_ip_pool=self.floating_ip_pool)
        file.update(resource=resource)
        return file

