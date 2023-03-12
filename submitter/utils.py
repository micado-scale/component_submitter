import random
import string
import json
import logging
import copy
import io

from ruamel.yaml import YAML, representer
from kubernetes import config as kubeconfig
from kubernetes.client.api import core_v1_api
from kubernetes.client.rest import ApiException
from kubernetes.stream import stream

from submitter.abstracts.exceptions import AdaptorCritical

logger = logging.getLogger("submitter." + __name__)

api = None


class NonAliasingRTRepresenter(representer.RoundTripRepresenter):
    """ Turn off auto-aliases in ruamel.yaml """

    def ignore_aliases(self, data):
        return True


yaml = YAML()
yaml.default_flow_style = False
yaml.preserve_quotes = True
yaml.Representer = NonAliasingRTRepresenter


def init_kubernetes():
    """Initialise kubernetes sdk from kubeconfig"""
    global api
    kubeconfig.load_kube_config()
    api = core_v1_api.CoreV1Api()


def get_pod_of_namespaced_deployment(deployment_name, namespace):
    """Get the first pod of a namespaced deployment"""
    if not api:
        raise NameError("Kube API not initialised!")
    try:
        return [
            pod.metadata.name
            for pod in api.list_namespaced_pod(namespace).items
            if pod.metadata.name.startswith(deployment_name)
        ][0]
    except IndexError as e:
        logger.error(f"Could not find {deployment_name} pod in {namespace}!")
        raise e from None


def exec_command_in_deployment(
    command, deployment_name, success=None, namespace="micado-system"
):
    """Exec a shell command in the first pod of a deployment, check success"""
    pod_name = get_pod_of_namespaced_deployment(deployment_name, namespace)
    exec_command = ["/bin/sh", "-c"]
    exec_command.append(command)
    try:
        resp = stream(
            api.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=exec_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        if success and success not in resp:
            logger.error(f"{pod_name} exec error: {resp}")
            raise AdaptorCritical(f"{pod_name} exec error!")
    except ApiException as e:
        logger.error(f"K8s API error: {e}")
        raise AdaptorCritical(f"K8s API error!")


def get_namespaced_secret(secret_name, namespace="micado-system"):
    """Get a secret in a namespace"""
    if not api:
        raise AdaptorCritical("Kube API not initialised!")
    try:
        return api.read_namespaced_secret(secret_name, namespace)
    except ApiException as e:
        logger.error(f"Could not read {secret_name} secret in {namespace}!")
        raise AdaptorCritical from e


def patch_namespaced_secret(secret_name, body, namespace="micado-system"):
    """Patch a secret"""
    if not api:
        raise AdaptorCritical("Kube API not initialised!")
    try:
        api.patch_namespaced_secret(secret_name, namespace, body)
    except ApiException as e:
        logger.error(f"Could not patch {secret_name} secret in {namespace}!")
        raise AdaptorCritical from e


def load_json(path):
    """ Load the dictionary from a json file """

    with open(path, "r") as file:
        data = json.load(file)

    return data


def dump_json(data, path):
    """ Dump the dictionary to a json file """

    with open(path, "w") as file:
        json.dump(data, file, indent=4)


def dump_order_yaml(data, path=None):
    """ Dump the dictionary to a yaml file """
    if not path:
        buffer = io.StringIO()
        yaml.dump(data, buffer)
        return buffer.getvalue()

    with open(path, "w") as file:
        yaml.dump(data, file)


def dump_list_yaml(data, path):
    """ Dump a list of dictionaries to a single yaml file """

    with open(path, "w") as file:
        yaml.dump_all(data, file)


def get_yaml_data(path, stream=False):
    """ Retrieve the yaml dictionary form a yaml file and return it """

    if stream:
        return yaml.load(path)

    with open(path, "r") as file:
        data = yaml.load(file)

    return data


def id_generator(size=8, chars=string.ascii_uppercase + string.digits):
    """ Generate an ID """
    return "".join(random.choice(chars) for _ in range(size))


def check_lifecycle(node, interface_type):
    """Check that an interface type is present """
    if [x for x in node.interfaces if interface_type in x.type]:
        return True
    else:
        try:
            return "create" in node.type_definition.interfaces[interface_type]
        except (AttributeError, KeyError, TypeError):
            return False


def get_lifecycle(node, interface_type):
    """Get inputs from TOSCA interfaces

    First, gets the interface from the direct parent, then updates it with the
    TOSCA interface inputs from the current node

    Returns:
        dict: a set of inputs for different lifecycle stages
    """
    # Get the interfaces from the first parent
    lifecycle = _get_parent_interfaces(node, interface_type)
    properties = {k: v.value for k, v in node.get_properties().items()}

    # Update these interfaces with any inputs from the current node
    interfaces = [x for x in node.interfaces if interface_type in x.type]
    for stage in interfaces:
        _update_parent_spec(lifecycle, stage)

    resolve_get_functions(
        lifecycle,
        "get_property",
        lambda x: isinstance(x, list),
        lambda x, y: y.get(x[1]),
        properties,
    )

    return lifecycle


def _get_parent_interfaces(node, interface_type):
    interfaces = {}
    try:
        parent_interfaces = node.type_definition.interfaces[interface_type]
        parent_interfaces = copy.deepcopy(parent_interfaces)
    except (AttributeError, KeyError, TypeError):
        parent_interfaces = {}

    for stage, value in parent_interfaces.items():
        if stage == "type":
            continue
        try:
            interfaces[stage] = value.get("inputs") or {}
        except AttributeError:
            interfaces[stage] = {}

    return interfaces


def _update_parent_spec(lifecycle, stage):
    lifecycle.setdefault(stage.name, {})
    if not stage.inputs:
        return

    try:
        lifecycle[stage.name]["spec"].update(stage.inputs["spec"])
        stage.inputs["spec"] = lifecycle[stage.name]["spec"]
    except KeyError:
        pass
    lifecycle[stage.name].update(stage.inputs)


def get_cloud_type(node, supported_clouds):
    """Get parent types of a node

    Returns the cloud type from node type or parent types

    Returns:
        string: lowercase node type
    """

    def generate_parents(node):
        while True:
            if not hasattr(node, "type"):
                break
            yield node.type.lower()
            node = node.parent_type

    for cloud in supported_clouds:
        if any(cloud in x for x in generate_parents(node)):
            return cloud


def get_cloud_config(
    insert_mode, runcmd_placeholder, default_cloud_config, tosca_cloud_config
):

    if insert_mode == "overwrite":
        return tosca_cloud_config

    elif insert_mode == "insert":
        for x, y in tosca_cloud_config.items():
            try:
                idx = default_cloud_config[x].index(runcmd_placeholder)
                default_cloud_config[x][idx:idx] = y
            except (AttributeError, KeyError):
                default_cloud_config[x] = y
            except (ValueError, TypeError):
                default_cloud_config[x] = y + default_cloud_config[x]

    else:
        for x, y in tosca_cloud_config.items():
            try:
                if isinstance(default_cloud_config[x], bool):
                    default_cloud_config[x] = y
                else:
                    default_cloud_config[x] += y
            except KeyError:
                default_cloud_config[x] = y

    return default_cloud_config


def resolve_get_functions(
    dict_to_search, key_to_find, test_result_fn, resolve_result_fn, *args
):
    """Recursively update a dict with TOSCA 'get' functions

    Args:
        dict_to_search (dict): Dictionary to iterate through
        key_to_find (str): 'get' function to search for (eg 'get_input')
        test_result_fn (func): Function to test the result
        resolve_result_fn (func): Function to resolve the result
        args (*): Extra args to pass to resolve_result_fn

    Returns:
        None: Modifies the dictionary in place
    """
    for key, value in dict_to_search.items():
        if key == key_to_find:
            return value

        elif isinstance(value, dict):
            result = resolve_get_functions(
                value, key_to_find, test_result_fn, resolve_result_fn, *args
            )
            if test_result_fn(result):
                dict_to_search[key] = resolve_result_fn(result, *args)

        elif isinstance(value, list):
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    continue
                result = resolve_get_functions(
                    item, key_to_find, test_result_fn, resolve_result_fn, *args
                )
                if test_result_fn(result):
                    dict_to_search[key][index] = resolve_result_fn(
                        result, *args
                    )
