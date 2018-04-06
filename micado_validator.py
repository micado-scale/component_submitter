from toscaparser.tosca_template import ToscaTemplate
import logging

MiCADOTYPES = ("tosca.relationships.AttachesTo","tosca.relationships.ConnectsTo",
        "tosca.relationships.HostedOn", "tosca.nodes.MiCADO.ObjectStorage.Docker",
        "tosca.nodes.MiCADO.Occopus.CloudSigma.Compute",
        "tosca.nodes.MiCADO.network.Network.Docker",
        "tosca.artifacts.Deployment.Image.Container.Docker",
        "tosca.nodes.MiCADO.Container.Application.Docker")

logger = logging.getLogger("submitter."+__name__)

class ValidationError(Exception):
    """Base error for validation"""

class MultiError(ValidationError):
    """For catching multiple errors"""
    def __init__(self, msg, error_set):
        super().__init__()

        self.msg = "--{}--".format(msg)
        print(self.msg)

        for error in error_set:
            self.msg += "\n  {}".format(error)
            print("  {}".format(error))

        print("----{}".format("-"*len(msg)))

class Validator():

    """The validator class"""

    def __init__(self, tpl):
        """ init """
        if isinstance(tpl, ToscaTemplate):
            self.tpl = tpl
        else:
            raise TypeError("Not a ToscaTemplate object")

        errors = set()
        for node in self.tpl.nodetemplates:
            errors.update(self._validate_repositories(node))
            errors.update(self._validate_types(node))
        if errors:
            logger.error("Incompatible TOSCA")
            raise MultiError("Validation Errors", sorted(errors))
        else:
            logger.info("Compatible TOSCA")


    def _validate_types(self, node):
        """ Validate MiCADO types """

        types = self._key_search(("type","relationship"), node.entity_tpl)
        return {
            "[NODE: {}] Type <{}> is not compatible".format(node.name, type)
            for type in types if "tosca." in type and type not in MiCADOTYPES
            }

    def _validate_repositories(self, node):
        """ Validate repository links """

        repo_names = [repo.name for repo in self.tpl.repositories]
        if not repo_names:
            return {"[*TPL] No repositories found!"}

        repositories = self._key_search("repository", node.entity_tpl)
        return {
            "[NODE: {}] Repository <{}> not defined!".format(node.name, repo)
            for repo in repositories if repo not in repo_names
            }

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
