"""
MiCADO Submission Engine TOSCA Validator
-----------------------------------------

Validate ToscaTemplate objects to ensure syntactic and semantic compatibility
with custom defined and TOSCA normative types.

Further validates a ToscaTemplate which has already passed validation steps
set out by the OpenStack ToscaParser. Currently validation checks exist for
repositories and the requirements and relationships of custom defined types.
"""


from toscaparser.tosca_template import ToscaTemplate
import utils
import logging

logger=logging.getLogger("adaptor."+__name__)

class ValidationError(Exception):
    """Base error for validation"""

class MultiError(ValidationError):
    """Errors occured during validation..."""
    def __init__(self, error_set, msg=None):
        super().__init__()
        msg = msg if msg else ""
        self.msg = "\n--{}--".format(msg)
        for error in error_set:
            self.msg += "\n  {}".format(error)
        self.msg += "\n----{}".format("-"*len(msg))

    def __str__(self):
        """Overload __str__ to return msg when printing/logging"""
        return self.msg

def validation(tpl):
    """ The validation process

    Runs validation steps on the given TOSCA Template, and builds an error
    list. Raises a MultiError on failed validation. On success, says so.

    :param tpl: The ToscaTemplate to validate
    :type tpl: ToscaTemplate <toscaparser.tosca_template.ToscaTemplate>
    :raises: TypeError, MultiError

    Usage:
        >>> from micado_validator import Validator

            Successful validation:

        >>> Validator().validation(<toscaparser.tosca_template.ToscaTemplate>)
        'ToscaTemplate passed compatibility validation'

            Errors during validation:

        >>> Validator(<toscaparser.tosca_template.ToscaTemplate>)
        micado_validator.MultiError:
        ----
        (...list of errors...)

    """
    if not isinstance(tpl, ToscaTemplate):
        logger.error("Got a non-ToscaTemplate object!")
        raise TypeError("Not a ToscaTemplate object")

    custom_types = tuple(tpl.topology_template.custom_defs.keys())
    errors = set()

    for node in tpl.nodetemplates:
        errors.update(validate_repositories(node, tpl.repositories))
        if _is_custom(node, custom_types):
            errors.update(validate_requirements(node))
            errors.update(validate_relationships(node))
            errors.update(validate_relationship_properties(node))

    if errors:
        logger.error("Incompatible ToscaTemplate!")
        raise MultiError(sorted(errors))#, "Validation Errors!")
    else:
        logger.info("ToscaTemplate object passed compatibility validation.")
        return "ToscaTemplate passed compatibility validation"


def validate_repositories(node, repositories):
    """ Validate repository names

    Checks to see if repositories have been defined at the top level, and if
    nodes reference those repositories correctly. Returns errors if not.

    """
    repository_names = [repository.name for repository in repositories]
    if not repository_names:
        return {"[*TPL] No repositories found!"}

    repositories = _key_search("repository", node.entity_tpl)
    return {
        "[NODE: {}] Repository <{}> not defined!".format(node.name, repo)
        for repo in repositories if repo not in repository_names
        }

def validate_requirements(node):
    """ Validate requirements and their syntax

    Checks that requirements in custom_types and in node definitions are
    defined as one-item lists and that node definition requirements correctly
    reference requirements defined in custom_types. Returns errors if not.

    """
    type_reqs = node.type_definition.requirements
    node_reqs = node.requirements

    type_req_names = _get_requirement_names(type_reqs)
    node_req_names = _get_requirement_names(node_reqs)

    msg = "Too many requirements per list item!"

    if len(type_reqs) != len(type_req_names):
        return {"[CUSTOM TYPE: {}] {}".format(node.type, msg)}

    elif len(node_reqs) != len(node_req_names):
        return {"[NODE: {}] {}".format(node.name, msg)}

    return {
        "[NODE: {}] Requirement <{}> not defined!".format(node.name, req)
        for req in node_req_names if req not in type_req_names
        }

def validate_relationships(node):
    """ Validate relationships

    Checks that relationships used in node definitions correctly reference
    relationships defined in TOSCA normative or custom types. Returns errors
    if not.

    """
    type_reqs = node.type_definition.requirements
    node_reqs = node.requirements
    errors = set()

    for node_req in node_reqs:
        relationships = _key_search(["relationship", "type"], node_req)
        supported_relationships = \
                    [_key_search(["relationship", "type"], type_req)
                     for type_req in type_reqs]

        errors.update({
            "[NODE: {}] "
            "Relationship <{}> not supported!".format(node.name, relationship)
            for relationship in relationships
            if relationship not in str(supported_relationships)
        })

    return errors

def validate_relationship_properties(node):
    """ Validate relationship properties

    Checks that relationships defined properties required by their definition
    in TOSCA normative or custom types. Returns errors if not.

    """
    errors = set()
    for req, prop, relation in _get_required_properties(node):
        if not _has_property(req, prop, relation):
            errors.update({
                "[NODE: {}] Relationship <{}> "
                "missing property <{}>".format(node.name, relation, prop)
                })
    return errors

def _is_custom(node, custom_types):
    """ Determine if node is of a custom type """
    return True if node.type in custom_types else False


def _has_property(requirements, prop, rel_type):
    """ Check if a requirement has the correct properties and type """
    for requirement_dict in requirements:
        for requirement in requirement_dict.values():
            if isinstance(requirement, str):
                return True
            relation = requirement.get("relationship")
            if isinstance(relation, dict) and rel_type in relation.get("type"):
                if prop in str(requirement_dict):
                    return True
    return False


def _get_requirement_names(req_dict):
    """ Get requirement names """
    return [requirement for requirements in
            [list(req.keys()) for req in req_dict]
            for requirement in requirements]


def _get_required_properties(node):
    """ Generate required properties """
    for relation in node.related.values():
        for prop, prop_obj in relation.get_properties_def().items():
            if prop_obj.required:
                yield (node.requirements, prop, relation.type)


def _key_search(query, node):
    """ Search through the raw data of a node for a value given a key """
    def flatten_pairs(nest):
        """ Recursively crawl through a nested dictionary """
        for key, val in nest.items():
            if isinstance(val, dict):
                yield from flatten_pairs(val)
            elif isinstance(val, list):
                for listitem in val:
                    if isinstance(listitem, dict):
                        yield from flatten_pairs(listitem)
            else:
                yield key, val

    return [val for key, val in flatten_pairs(node) if key in query]
