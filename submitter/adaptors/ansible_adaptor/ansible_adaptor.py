import logging
from pathlib import Path

import ansible_runner
from toscaparser.tosca_template import ToscaTemplate


from submitter import utils
from submitter.submitter_config import DEFAULTS
from submitter.abstracts import base_adaptor
from submitter.abstracts.exceptions import AdaptorCritical
from submitter.adaptors.ansible_adaptor.handlers import HANDLERS

logger = logging.getLogger("adaptors.ansible_adaptor")

ROTATION = 100  # max number of artifacts (logs, etc...) to keep
QUIET = True  # hide ansible output

class AnsibleAdaptor(base_adaptor.Adaptor):
    def __init__(
        self,
        adaptor_id,
        config,
        dryrun=False,
        validate=False,
        template: ToscaTemplate = None,
    ):
        self.id = adaptor_id
        self.config = config

        self.output_path = get_output_dir(adaptor_id, config)
        self.dryrun = dryrun
        self.tpl = template
        
        self.playbook_paths_files = []

    def translate(self, to_list=False):
        """Create configs"""


        for handler, handle_fn in HANDLERS.items():
            logger.debug(f"Running {handler} handler.")
            self.playbook_paths_files.append(
                handle_fn(
                    self.tpl.nodetemplates,
                    self.output_path,
                    self.config
                )
            )
            
        if to_list:
            return self.playbook_paths_files
        


    def execute(self):
        
        for path, file in self.playbook_paths_files:
            ansible_runner.interface.run(
                ident=self.id,
                playbook=file,
                private_data_dir=path,
                rotate_artifacts=ROTATION,
                quiet=QUIET,
            )


    def update(self):
        raise NotImplementedError

    def undeploy(self):
        raise NotImplementedError

    def cleanup(self):
        raise NotImplementedError


def get_output_dir(app_id, config) -> Path:
    """Creates a directory for this app's playbooks"""
    output_path = Path(config.get("volume", DEFAULTS["out_path"]))
    output_path = output_path / f"{app_id}_Playbooks"
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path
