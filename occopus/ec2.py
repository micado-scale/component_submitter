CAPABILITIES = (NUM_CPUS, DISK_SIZE, MEM_SIZE, REGION_NAME, IMAGE_ID, INSTANCE_TYPE, KEY_NAME,
			   SECURITY_GROUP_IDS, SUBNET_ID ) = \
	          ('num_cpus', 'disk_size', 'mem_size', 'region_name', 'image_id', 'instance_type', 'key_name'
			   'security_group_ids', 'subnet_id')

ENDPOINT = 'endpoint_cloud'

class EC2(object):
  def __init__(self, node):
    capabilities = node.get_capability("host")
    self._set_endpoint(node.get_property_value("cloud")[ENDPOINT])
    for n in CAPABILITIES:
      self._set_params(n, capabilities.get_property_value(n))

  def _set_params(self, param, value):
	if param is NUM_CPUS:
	  self._set_num_cpus(value)
	elif param is DISK_SIZE:
	  self._set_disk_size(value)
	elif param is MEM_SIZE:
	  self._set_mem_size(value)
	elif param is REGION_NAME:
	  self._set_region_name(value)
	elif param is IMAGE_ID:
	  self._set_image_id(value)
	elif param is INSTANCE_TYPE:
	  self._set_instance_type(value)
	elif param is KEY_NAME:
	  self._set_key_name(value)
	elif param is SECURITY_GROUP_IDS:
	  self._set_security_group_ids(value)
	elif param is SUBNET_ID:
	  self._set_subnet_id(value)
	else:
	  raise BaseException("param not related to EC2")


  def _set_num_cpus(self, num_cpus):
    self.num_cpus = num_cpus
  def _set_disk_size(self, disk_size):
    self.disk_size = disk_size
  def _set_mem_size(self, mem_size):
    self.mem_size = mem_size
  def _set_region_name(self, region_name):
    self.region_name = region_name
  def _set_image_id(self, image_id):
    self.image_id = image_id
  def _set_instance_type(self, instance_type):
    self.instance_type = instance_type
  def _set_key_name(self, key_name):
    self.key_name = key_name
  def _set_security_group_ids(self, security_group_ids):
    self.security_group_ids = security_group_ids
  def _set_subnet_id(self, subnet_id):
	self.subnet_id = subnet_id
  def _set_endpoint(self, endpoint):
	self.endpoint = endpoint

  def get_num_cpus(self):
	  return self.num_cpus
  def get_disk_size(self):
	  return self.disk_size
  def get_mem_size(self):
	  return self.mem_size
  def get_region_name(self):
	  return self.region_name
  def get_image_id(self):
	  return self.image_id
  def get_instance_type(self):
	  return self.instance_type
  def get_key_name(self):
	  return self.key_name
  def get_security_group_ids(self):
	  return self.security_group_ids
  def get_subnet_id(self):
	  return self.subnet_id
  def get_enpoint(self):
	  return self.endpoint

  def file(self):
	file = dict()
	resource = dict()
	resource.update(type='nova', endpoint=self.endpoint, regionname=self.region_name, image_id=self.region_name,
					instance_type=self.instance_type, key_name=self.key_name, security_group_ids=self.security_group_ids,
					subnet_id=self.subnet_id)