#!/usr/bin/python
CAPABILITIES = (NUM_CPUS, DISK_SIZE, MEM_SIZE, DEPLOYMENT_ID, INSTANCE_TYPE_ID, KEY_PAIR_ID,OPENED_PORT) = \
    ('num_cpus', 'disk_size', 'mem_size', 'deployment_id', 'instance_type_id',
     'key_pair_id', 'opened_port')

ENDPOINT = 'endpoint_cloud'
import yaml
class CloudSigma():

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
        elif param is DEPLOYMENT_ID:
            self._set_deployment_id(value)
        elif param is INSTANCE_TYPE_ID:
            self._set_instance_type_id(value)
        elif param is KEY_PAIR_ID:
            self._set_key_pair_id(value)
        elif param is OPENED_PORT:
            self._set_opened_port(value)
        else:
            raise BaseException("param not related to CloudBroker")

    def _set_num_cpus(self, num_cpus):
        self.num_cpus = num_cpus
    def _set_disk_size(self, disk_size):
        self.disk_size = disk_size
    def _set_mem_size(self, mem_size):
        self.mem_size = mem_size
    def _set_deployment_id(self, deployment_id):
        self.deployment_id = deployment_id
    def _set_instance_type_id(self, instance_type_id):
        self.instance_type_id = instance_type_id
    def _set_key_pair_id(self, key_pair_id):
        self.key_pair_id = key_pair_id
    def _set_opened_port(self, opened_port):
        self.opened_port = opened_port
    def _set_endpoint(self, endpoint):
        self.endpoint = endpoint

    def get_num_cpu(self):
        return self.num_cpus
    def get_disk_size(self):
        return self.disk_size
    def get_mem_size(self):
        return self.get_mem_size()
    def get_deployment_id(self):
        return self.deployment_id
    def get_instance_type_id(self):
        return self.instance_type_id
    def get_key_pair_id(self):
        return self.key_pair_id
    def get_opened_port(self):
        return self.opened_port
    def get_endpoint(self):
        return self.get_endpoint()

    def file(self):
        file = dict()
        resource = dict()
        description = dict()

        description.update(deployment_id=self.deployment_id, instance_type_id=self.instance_type_id, key_pair_id=self.key_pair_id, opened_port=self.opened_port)
        resource.update(type="cloudbroker",endpoint=self.endpoint, description=description)
        file.update(resource=resource)
        return file

