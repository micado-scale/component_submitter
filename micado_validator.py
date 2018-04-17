from toscaparser.tosca_template import ToscaTemplate
import logging

logger = logging.getLogger("submitter."+__name__)

class ValidationError(Exception):
    """Base error for validation"""

class MultiError(ValidationError):
    """For catching multiple errors"""
    def __init__(self, msg, error_set):
        """ init """
        super().__init__()

        self.msg = "Validation Error!\n--{}--".format(msg)
        for error in error_set:
            self.msg += "\n  {}".format(error)
        self.msg += "\n----{}".format("-"*len(msg))

        print (self.msg)

    def __str__(self):
        """Overload __str__ to return msg when printing/logging"""
        return self.msg

class Validator():
    """The validator class"""

    def __init__(self, tpl=None):
        """ init """

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
            logger.debug("Incompatible TOSCA")
            raise MultiError("Error List", sorted(errors))
        else:
            logger.debug("Compatible TOSCA")

    def _validate_repositories(self, node, repositories):
        """ Validate repository names """

        repo_names = [repo.name for repo in repositories]
        if not repo_names:
            return {"[*TPL] No repositories found!"}

        repositories = self._key_search("repository", node.entity_tpl)
        return {
            "[NODE: {}] Repository <{}> not defined!".format(node.name, repo)
            for repo in repositories if repo not in repo_names
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
            supported_relationships = [self._key_search(["relationship","type"], type_req) for type_req in type_reqs]
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
            for requirement_dict in requirements:
                for requirement in requirement_dict.values():
                    relation = requirement.get("relationship")
                    if isinstance(relation, dict) and type in relation.get("type"):
                        if property in str(requirement_dict): return True
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
        """ Determines if node is of a custom type """
        return True if node.type in self.custom_types else False

    def _key_search(self, query, node):
        """ Search through the node for a key """
        def flatten_pairs(nest):
            """ Crawl through nests """
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
