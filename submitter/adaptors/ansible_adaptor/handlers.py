import jinja2
import os
import shutil

import submitter.adaptors.ansible_adaptor.templates as templates

jinja_loader = jinja2.FileSystemLoader(searchpath=templates.__path__)
jinja_env = jinja2.Environment(loader=jinja_loader)

## Avoiding dynamic imports now, but if we get more than
## one handler, we should probably create separate modules
## for each handler and trash this file.

def handle_edge_playbook(nodes, out_path, config):
    """Handle edge playbook configuration"""
    VERSION = "v0.12.3"

    edge_info = get_edge_node_info(nodes)
    if not edge_info:
        return
    edge_info["micado_host"] = config.get("micado_host", "localhost")

    edge_path = os.path.join(out_path, "micado-edge")
    edge_info["edge_path"] = edge_path

    prepare_edge_playbook(VERSION, edge_path)
    write_private_key(edge_info["edges"], edge_path)

    template = jinja_env.get_template(f"micado-edge/{VERSION}/hosts.yml.j2")
    template = template.render(**edge_info)

    hosts_path = os.path.join(
        edge_path, "inventory/hosts.yml"
    )

    with open(hosts_path, 'w') as f:
        f.write(template)

    return (edge_path, "edge.yml")

def write_private_key(edges, out_path):
    """Write private keys to files"""
    for edge, props in edges.items():
        if not props.get("ssh_private_key"):
            continue
        
        key_path = os.path.join(out_path, f"{edge}.pem")
        with open(key_path, 'w') as f:
            f.write(props["ssh_private_key"].strip() + '\n')
        
        os.chmod(key_path, 0o600)

def prepare_edge_playbook(version, out_path):
    """Copy edge playbook to output directory"""
    shutil.copytree(
        os.path.join(templates.__path__[0], f"micado-edge/{version}/playbook"),
        out_path,
        dirs_exist_ok=True
    )

def get_edge_node_info(nodes):
    """Get edge node information"""
    NODE_TYPES = ["tosca.nodes.MiCADO.Edge"]
    edges = [node for node in nodes if node.type in NODE_TYPES]
    return {
        "edges": { 
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
