import jinja2
import os
import shutil

import submitter.adaptors.ansible_adaptor.templates as templates
from submitter.adaptors.ansible_adaptor.playbook import Playbook

jinja_loader = jinja2.FileSystemLoader(searchpath=templates.__path__)
jinja_env = jinja2.Environment(loader=jinja_loader)

## Avoiding dynamic imports now, but if we get more than
## one handler, we should probably create separate modules
## for each handler and trash this file.

def handle_edge_playbook(nodes, out_path):
    """Handle edge playbook configuration"""
    VERSION = "v0.12.0"

    edge_info = get_edge_node_info(nodes)

    edge_path = os.path.join(out_path, "micado-edge")

    if not edge_info:
        return

    shutil.copytree(
        os.path.join(templates.__path__[0], f"micado-edge/{VERSION}/playbook"),
        edge_path,
        dirs_exist_ok=True
    )

    for edge, props in edge_info["edges"].items():
        if not props.get("ssh_private_key"):
            continue
        
        with open(os.path.join(edge_path, f"{edge}.pem"), 'w') as f:
            f.write(props["ssh_private_key"])

    template = jinja_env.get_template(f"micado-edge/{VERSION}/hosts.yml.j2")
    template = template.render(**edge_info)

    hosts_path = os.path.join(
        edge_path, "inventory/hosts.yml"
    )

    with open(hosts_path, 'w') as f:
        f.write(template)

    return (edge_path, "edge.yml")

def prepare_edge_playbook(version, out_path):
    micado_playbook = Playbook(
        url=f"https://github.com/micado-scale/ansible-micado/tarball/{version}"
    )
    micado_playbook.download()
    micado_playbook.extract(out_path)

def get_edge_node_info(nodes):
    NODE_TYPES = ["tosca.nodes.MiCADO.Edge"]
    edges = [node for node in nodes if node.type in NODE_TYPES]
    return {"edges": { 
        edge.name: {
            property: edge.get_property_value(property)
            for property in edge.get_properties()
        }
        for edge in edges
    }
    }



HANDLERS = {
    "micado.Edge": handle_edge_playbook,
}
