"""
component_submitter.micado_validator
----------------------------------

A compatibility validator for ToscaTemplate objects.
"""

import logging

from toscaparser.tosca_template import ToscaTemplate

logger = logging.getLogger("submitter."+__name__)

class ValidationError(Exception):
    """Base error for validation"""

class MultiError(ValidationError):
    """Errors occured during validation..."""
    def __init__(self, msg, error_set):
        super().__init__()
        self.msg = "\n--{}--".format(msg)
        for error in error_set:
            self.msg += "\n  {}".format(error)
        self.msg += "\n----{}".format("-"*len(msg))

    def __str__(self):
        """Overload __str__ to return msg when printing/logging"""
        return self.msg

class Validator():

    """ The MiCADO Validator class

    Further validates a ToscaTemplate which has already passed validation steps
    set out by the OpenStack ToscaParser. Currently validation checks exist for
    repositories and the requirements and relationships of custom defined types.

    :param tpl: The ToscaTemplate to validate
    :type tpl: ToscaTemplate <toscaparser.tosca_template.ToscaTemplate>
    :raises: TypeError, MultiError

    Usage:
        >>> from micado_validator import Validator

            Successful validation:

        >>> Validator(<toscaparser.tosca_template.ToscaTemplate>)
        <micado_validator.Validator object>

            Errors during validation:

        >>> Validator(<toscaparser.tosca_template.ToscaTemplate>)
        ----Validation Errors!----
        (...list of errors...)

    """

    def __init__(self, tpl):

        if not isinstance(tpl, ToscaTemplate):
            logger.error("Got a non-ToscaTemplate object!")
            raise TypeError("Not a ToscaTemplate object")

        self.custom_types = tuple(tpl.topology_template.custom_defs.keys())
        errors = set()

        for node in tpl.nodetemplates:
            errors.update(self._validate_repositories(node, tpl.repositories))
            if self._is_custom(node):
                errors.update(self._validate_requirements(node))
                errors.update(self._validate_relationships(node))
        if errors:
            logger.error("Incompatible ToscaTemplate!")
            raise MultiError("Validation Errors!", sorted(errors))
        else:
            logger.info("ToscaTemplate object passed compatibility validation.")

    def _validate_repositories(self, node, repositories):
        """ Validate repository names """

        repository_names = [repository.name for repository in repositories]
        if not repository_names:
            return {"[*TPL] No repositories found!"}

        repositories = self._key_search("repository", node.entity_tpl)
        return {
            "[NODE: {}] Repository <{}> not defined!".format(node.name, repo)
            for repo in repositories if repo not in repository_names
            }

    def _validate_requirements(self, node):
        """ Validate requirements"""

        type_reqs = node.type_definition.requirements
        node_reqs = node.requirements

        if not isinstance (type_reqs, list):
            return {
            "[CUSTOM TYPE: {}] Requirements not formatted as list".format(node.type)
                }
        if not isinstance (node_reqs, list):
            return {
            "[NODE: {}] Requirements not formatted as list".format(node.name)
                }

        type_req_names = [ requirement for requirements in
            [list(req.keys()) for req in type_reqs]
                for requirement in requirements ]

        node_req_names = [ requirement for requirements in
            [list(req.keys()) for req in node_reqs]
                for requirement in requirements ]

        if len(type_reqs) != len(type_req_names):
            return {
            "[CUSTOM TYPE: {}] "
            "Too many requirements per list item".format(node.type)
                }
        if len(node_reqs) != len(node_req_names):
            return {
            "[NODE: {}] "
            "Too many requirements per list item".format(node.name)
                }

        errors = {
            "[NODE: {}] Requirement <{}> not defined!".format(node.name, req)
            for req in node_req_names if req not in type_req_names
            }

        for node_req in node_reqs:
            relationships = self._key_search(["relationship","type"], node_req)
            supported_relationships = \
                        [self._key_search(["relationship","type"], type_req)
                         for type_req in type_reqs]

            errors.update({
                    "[NODE: {}] Relationship <{}> not supported!"
                    .format(node.name, relationship)
                    for relationship in relationships
                    if relationship not in str(supported_relationships)
                })

        return errors

    def _validate_relationships(self, node):
        """ Validate relationships"""

        def has_property(requirements, property, type):
            """ Check if a requirement has the correct properties and type """
            for requirement_dict in requirements:
                for requirement in requirement_dict.values():
                    relation = requirement.get("relationship")
                    if isinstance(relation, dict) and type in relation.get("type"):
                        if property in str(requirement_dict):
                            return True
            return False

        for target_node, relation in node.related.items():
            for property, prop_obj in relation.get_properties_def().items():
                if prop_obj.required:
                    if not has_property(node.requirements, property, relation.type):
                        return {
                            "[NODE: {}] Relationship <{}> missing property <{}>"
                            .format(node.name, relation.type, property)
                            }
        return set()

    def _is_custom(self,node):
        """ Determine if node is of a custom type """
        return True if node.type in self.custom_types else False

    def _key_search(self, query, node):
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
