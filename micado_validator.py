"""
component_submitter.micado_validator
------------------------------------

A compatibility validator for ToscaTemplate objects.
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
        self.msg = f'\n--{msg}--'
        for error in error_set:
            self.msg += f'\n  {error}'
        self.msg += f'\n----{"-"*len(msg)}'

    def __str__(self):
        """Overload __str__ to return msg when printing/logging"""
        return self.msg

class Validator():

    """ The MiCADO Validator class

    Further validates a ToscaTemplate which has already passed validation steps
    set out by the OpenStack ToscaParser. Currently validation checks exist for
    repositories and the requirements and relationships of custom defined types.

    """

    def validation(self, tpl):
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

<<<<<<< HEAD

=======
            >>> Validator(<toscaparser.tosca_template.ToscaTemplate>)
            micado_validator.MultiError:
            ----
            (...list of errors...)

        """
>>>>>>> upstream/dev
        if not isinstance(tpl, ToscaTemplate):
            logger.error("Got a non-ToscaTemplate object!")
            raise TypeError("Not a ToscaTemplate object")

        self.custom_types = tuple(tpl.topology_template.custom_defs.keys())
        errors = set()

        for node in tpl.nodetemplates:
            errors.update(self.validate_repositories(node, tpl.repositories))
            if self._is_custom(node):
                errors.update(self.validate_requirements(node))
                errors.update(self.validate_relationships(node))
                errors.update(self.validate_relationship_properties(node))

        if errors:
            logger.error("Incompatible ToscaTemplate!")
            raise MultiError(sorted(errors))#, "Validation Errors!")
        else:
            logger.info("ToscaTemplate object passed compatibility validation.")
            return f'ToscaTemplate passed compatibility validation'


    def validate_repositories(self, node, repositories):
        """ Validate repository names

        Checks to see if repositories have been defined at the top level, and if
        nodes reference those repositories correctly. Returns errors if not.

        """
        repository_names = [repository.name for repository in repositories]
        if not repository_names:
            return {"[*TPL] No repositories found!"}

        repositories = self._key_search("repository", node.entity_tpl)
        return {
            f'[NODE: {node.name}] Repository <{repo}> not defined!'
            for repo in repositories if repo not in repository_names
            }

    def validate_requirements(self, node):
        """ Validate requirements and their syntax

        Checks that requirements in custom_types and in node definitions are
        defined as one-item lists and that node definition requirements correctly
        reference requirements defined in custom_types. Returns errors if not.

        """
        type_reqs = node.type_definition.requirements
        node_reqs = node.requirements

        type_req_names = self._get_requirement_names(type_reqs)
        node_req_names = self._get_requirement_names(node_reqs)

        msg = "Too many requirements per list item!"

        if len(type_reqs) != len(type_req_names):
            return {f'[CUSTOM TYPE: {node.type}] {msg}'}

        elif len(node_reqs) != len(node_req_names):
            return {f'[NODE: {node.name}] {msg}'}

        return {
            f'[NODE: {node.name}] Requirement <{req}> not defined!'
            for req in node_req_names if req not in type_req_names
            }

    def validate_relationships(self, node):
        """ Validate relationships

        Checks that relationships used in node definitions correctly reference
        relationships defined in TOSCA normative or custom types. Returns errors
        if not.

        """
        type_reqs = node.type_definition.requirements
        node_reqs = node.requirements
        errors = set()

        for node_req in node_reqs:
            relationships = self._key_search(["relationship","type"], node_req)
            supported_relationships = \
                        [self._key_search(["relationship","type"], type_req)
                         for type_req in type_reqs]

            errors.update({
                    f'[NODE: {node.name}] '
                    f'Relationship <{relationship}> not supported!'
                    for relationship in relationships
                    if relationship not in str(supported_relationships)
                })

        return errors

    def validate_relationship_properties(self, node):
        """ Validate relationship properties

        Checks that relationships defined properties required by their definition
        in TOSCA normative or custom types. Returns errors if not.

        """
        errors = set()
        for req, prop, relation in self._get_required_properties(node):
            if not self._has_property(req, prop, relation):
                errors.update({
                    f'[NODE: {node.name}] Relationship <{relation}> '
                    f'missing property <{prop}>'
                    })
        return errors

    def _has_property(self, requirements, property, type):
        """ Check if a requirement has the correct properties and type """
        for requirement_dict in requirements:
            for requirement in requirement_dict.values():
                relation = requirement.get("relationship")
                if isinstance(relation, dict) and type in relation.get("type"):
                    if property in str(requirement_dict):
                        return True
        return False

    def _get_requirement_names(self, req_dict):
        """ Get requirement names """
        return [ requirement for requirements in
            [list(req.keys()) for req in req_dict]
                for requirement in requirements ]

    def _get_required_properties(self, node):
        """ Generate required properties """
        for relation in node.related.values():
            for property, prop_obj in relation.get_properties_def().items():
                if prop_obj.required:
                    yield (node.requirements, property, relation.type)

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
