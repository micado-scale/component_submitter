import os
import tarfile
from pathlib import Path

import requests

TMP_DIR = Path("/tmp")


class Playbook:
    def __init__(self, url, path_in_tar = "playbook/"):
        self.url = url
        self.path = Path()
        self.path_in_tar = Path(path_in_tar)
        self.tmp_tar = TMP_DIR / Path(url).name

    def download(self):
        """Download playbook from GitHub to TMP_DIR."""
        r = requests.get(self.url, stream=True)

        TMP_DIR.mkdir(exist_ok=True)
        with open(self.tmp_tar, "wb") as f:
            f.write(r.content)

        if not tarfile.is_tarfile(self.tmp_tar):
            os.remove(self.tmp_tar)
            raise TypeError(f"Download failed - check tarfile at {self.url} exists.")

    def extract(self, out_dir):
        """Extract tar to the output directory"""
        if not os.path.isfile(self.tmp_tar):
            raise FileNotFoundError("Playbook tarball not found. Cannot extract.")

        tar_file = tarfile.open(self.tmp_tar)
        untar_path = Path(out_dir) / tar_file.firstmember.name

        tar_file.extractall(untar_path)
        tar_file.close()

        self.path = (Path(out_dir) / "ansible-micado")

        self.tmp_tar.unlink()  # delete the tarball
