#!/usr/bin/python
SELECTION = (NUM_CPUS, DISK_SIZE, MEM_SIZE, LIBDRIVE_ID, VCN_PASSWORD,
             HOST_NAME, PUBLISH_KEY_ID, FIREWALL_POLICY, DESCRIPTION) = \
    ('num_cpus', 'disk_size', 'mem_size', 'libdrive_id', 'vcn_password',
     'host_name', 'publish_key_id', 'firewall_policy', 'description')
class CloudSigma():

    def __init__(self, node):
        capabilities = node.get_capability("host")
        for n in  SELECTION:
          self._set_params(n,capabilities.get_property_value(n))

    def _set_params(self, param, value):
        if param is NUM_CPUS:
            self._set_num_cpus(value)
        elif param is DISK_SIZE:
            self._set_disk_size(value)
        elif param is MEM_SIZE:
            self._set_mem_size(value)
        elif param is LIBDRIVE_ID:
            self._set_libdrive_id(value)
        elif param is VCN_PASSWORD:
            self._set_vcn_password(value)
        elif param is HOST_NAME:
            self._set_host_name(value)
        elif param is PUBLISH_KEY_ID:
            self._set_publish_key_id(value)
        elif param is FIREWALL_POLICY:
            self._set_firewall_policy(value)
        elif param is DESCRIPTION:
            self._set_description(value)
        else:
            raise BaseException("param not related to CloudSigma")

    def _set_num_cpus(self, num_cpus):
        self.num_cpus = num_cpus
    def _set_disk_size(self, disk_size):
        self.disk_size = disk_size
    def _set_mem_size(self, mem_size):
        self.mem_size = mem_size
    def _set_libdrive_id(self, libdrive_id):
        self.libdrive_id = libdrive_id
    def _set_vcn_password(self, vcn_password):
        self.vcn_password = vcn_password
    def _set_host_name(self, host_name):
        self.host_name = host_name
    def _set_publish_key_id(self, publish_key_id):
        self.publish_key_id = publish_key_id
    def _set_firewall_policy(self, firewall_policy):
        self.firewall_policy = firewall_policy
    def _set_description(self, description):
        self.description = description

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
