import unittest

from toscaparser.tosca_template import ToscaTemplate

from adaptors.docker_adaptor import DockerAdaptor

class TestDockerAdaptor(unittest.TestCase):
    """ UnitTests for docker adaptor """

    def setUp(self):
        """ Prep a good TOSCA template """
        self.tpl = ToscaTemplate("tests/templates/good_tosca.yaml")
        self.adapt = DockerAdaptor("main_adapt", self.tpl)
        self.compose_data = {}

    def test_compose_properties_services(self):
        node = self.tpl.nodetemplates[0]
        key = "services"
        dic = {key: {"jobber":{"entrypoint":"echo entry","command":"sleep 10"}}}
        self.adapt._compose_properties(node, key)
        self.assertDictEqual(self.adapt.compose_data, dic)

    def test_compose_properties_networks(self):
        node = self.tpl.nodetemplates[5]
        key = "networks"
        dic = {key: {"stressynet":{"driver":"overlay"}}}
        self.adapt._compose_properties(node, key)
        self.assertDictEqual(self.adapt.compose_data, dic)

    def test_compose_properties_volumes(self):
        node = self.tpl.nodetemplates[6]
        key = "volumes"
        dic = {key: {"busydata":{}}}
        self.adapt._compose_properties(node, key)
        self.assertDictEqual(self.adapt.compose_data, dic)

    def test_compose_properties_inputs_default(self):
        node = self.tpl.nodetemplates[2]
        key = "services"
        dic = {key: {"db":{"ports":["6379:6379"]}}}
        self.adapt._compose_properties(node, key)
        self.assertDictEqual(self.adapt.compose_data, dic)

    def test_compose_properties_inputs_parsed(self):
        tpl = ToscaTemplate(
            "tests/templates/good_tosca.yaml", {"exposed_ports":["5959:5959"]})
        adapt = DockerAdaptor("other_adapt", tpl)
        node = tpl.nodetemplates[2]
        key = "services"
        dic = {key: {"db":{"ports":["5959:5959"]}}}
        adapt._compose_properties(node, key)
        self.assertDictEqual(adapt.compose_data, dic)

    def test_compose_requirements_attaches(self):
        node = self.tpl.nodetemplates[0]
        dic = {"services": {"jobber":{"volumes":["busydata:/tmp"]}},
               "volumes": {"busydata": {}}}
        self.adapt._compose_requirements(node)
        self.assertDictEqual(self.adapt.compose_data, dic)

    def test_compose_requirements_connects(self):
        node = self.tpl.nodetemplates[3]
        dic = {"services": {"updater": {"networks":["stressnet"]},
                            "db": {"networks":["stressnet"]}},
               "networks": {"stressnet": {"driver": "overlay"}}}
        self.adapt._compose_requirements(node)
        self.assertDictEqual(self.adapt.compose_data, dic)

    #test when implmented    
    def not_test_compose_requirements_hosts(self):
        node = self.tpl.nodetemplates[2]
        dic = {"services": {"db": {"deploy": {"placement":
                {"constraints": ["node.labels.host == MICADO-worker"]}}}}}
        self.adapt._compose_requirements(node)
        self.assertDictEqual(self.adapt.compose_data, dic)

    def test_create_compose_volume(self):
        dic = {"volumes": {"volume": {}},
               "services": {"node":{"volumes":["volume:location"]}}}
        self.adapt._create_compose_volume("node", "volume", "location")
        self.assertDictEqual(self.adapt.compose_data, dic)

    def test_create_compose_connection(self):
        dic = {"networks": {"network": {"driver":"overlay"}},
               "services": {"node":{"networks":["network"]},
                            "target":{"networks":["network"]}}}
        self.adapt._create_compose_connection("node", "target", "network")
        self.assertDictEqual(self.adapt.compose_data, dic)

    def test_create_compose_constraint(self):
        dic = {"services": {"node": {"deploy":
                {"placement": {"constraints": ["node.labels.host == host"]}}}}}
        self.adapt._create_compose_constraint("node", "host")
        self.assertDictEqual(self.adapt.compose_data, dic)

if __name__ == '__main__':
    unittest.main()
