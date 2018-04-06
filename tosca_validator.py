from toscaparser.tosca_template import ToscaTemplate

class Validator():
    """The validator class"""

    def __init__(self, tpl):
        """ init """
        tpl = ToscaTemplate("tosca.yaml")
        if isinstance(tpl,ToscaTemplate):
            self.tpl = tpl
        else:
            raise TypeError("Not a ToscaTemplate object")

        self._validate_repositories()

    def _key_search(self, query):
        """ Search through the tpl for a key """
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

        found = []
        for key, val in flatten_pairs(self.tpl.topology_template.tpl):
            if key == query:
                found.append(val)
        return found

    def _validate_repositories(self):
        """ Validate repository links """

        repo_names = [repo.name for repo in self.tpl.repositories]
        if not repo_names:
            raise KeyError("No repositories found!")
        for repo in self._key_search("repository"):
            if repo not in repo_names:
                raise KeyError("Repository not defined!")
