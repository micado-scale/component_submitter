import copy

from submitter.utils import resolve_get_inputs


def resolve_occurrences(tpl_dict, parsed_params):
    """
    Handle TOSCA v1.3 occurrences feature, for now
    """
    nodes = tpl_dict.get("topology_template", {}).get("node_templates")
    inputs = _determine_inputs(tpl_dict, parsed_params)
    nodes_with_occurrences = [
        node for node in nodes if "occurrences" in nodes[node]
    ]
    print(nodes_with_occurrences)
    for node in nodes_with_occurrences:
        new_nodes = _create_occurrences(node, nodes.pop(node), inputs)
        nodes.update(new_nodes)


def _determine_inputs(tpl_dict, parsed_params):
    """
    Store input values from parsed_params or defaults
    """
    params = parsed_params if parsed_params else {}
    inputs = tpl_dict.get("topology_template", {}).get("inputs", {})
    values = {}
    for key, value in inputs.items():
        values[key] = params.get(key) or value["default"]
    return values


def _create_occurrences(name, node, inputs):
    """
    Create and return a dictionary of new occurrences
    """
    occurrences = node.pop("occurrences")
    count = node.pop("instance_count", occurrences[0])
    if isinstance(count, str):
        count = int(count)
    elif isinstance(count, dict):
        try:
            count = int(inputs[count["get_input"]])
        except (KeyError, TypeError):
            raise KeyError("Could not resolve instance_count")

    new_nodes = {}
    for i in range(count):
        new_name = f"{name}-{i+1}"
        new_node = copy.deepcopy(node)
        resolve_get_inputs(
            new_node,
            _set_indexed_input,
            lambda x: isinstance(x, list),
            inputs,
            i,
        )

        new_nodes[new_name] = new_node

    return new_nodes


def _set_indexed_input(result, inputs, index):
    """
    Set the value of indexed inputs
    """
    if result[1] != "INDEX":
        raise TypeError("Unrecognised get_input format")
    try:
        return inputs[result[0]][index]
    except IndexError:
        raise IndexError(
            f"Input '{result[0]}' does not match node occurrences!"
        ) from None
