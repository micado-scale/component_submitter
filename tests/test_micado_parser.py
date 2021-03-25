import unittest


from submitter.micado_parser import set_template


class TestMicadoParser(unittest.TestCase):
    """ UnitTests for micado_parser """

    def test_parse_adt_from_url(self):
        tpl = set_template("https://raw.githubusercontent.com/micado-scale/ansible-micado/develop/demos/wordpress/wordpress_ec2.yaml")
        self.assertIn("wordpress", [x.name for x in tpl.nodetemplates])
        
    def test_parse_adt_from_file(self):
        tpl = set_template("tests/templates/good_tosca.yaml")
        self.assertIn("stressynet", [x.name for x in tpl.nodetemplates])

    def test_tosca_occurences_feature(self):
        tpl = set_template("tests/templates/adt_fd.yaml")
        self.assertIn("fd-receiver-6", [x.name for x in tpl.nodetemplates])


if __name__ == "__main__":
    unittest.main()
