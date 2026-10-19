"""Reading where a registry layer lives, with git (Plan B, spec §8.2). Each test makes a real
repository: a fake would test the fake."""

import subprocess

from comeni_core.artifact.lockfile import Locator
from mendel_compiler.locate import locate, locators


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                        "HOME": str(cwd), "PATH": "/usr/bin:/bin"})


def _repo(tmp_path, origin="https://github.com/comeni-project/comeni-registry"):
    repo = tmp_path / "repo"
    layer = repo / "layer"
    layer.mkdir(parents=True)
    (layer / "contract.yml").write_text("id: x\n")
    (repo / "elsewhere.txt").write_text("a\n")
    _git("init", "-q", cwd=repo)
    _git("add", ".", cwd=repo)
    _git("commit", "-q", "-m", "one", cwd=repo)
    if origin:
        _git("remote", "add", "origin", origin, cwd=repo)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                          text=True, check=True).stdout.strip()
    return repo, layer, head


def test_a_clean_layer_names_its_remote_and_commit(tmp_path):
    _repo_, layer, head = _repo(tmp_path)
    assert locate(layer) == Locator(source="https://github.com/comeni-project/comeni-registry",
                                    commit=head, dirty=False, path="layer")


def test_an_edited_layer_is_dirty_and_an_edit_beside_it_is_not(tmp_path):
    repo, layer, _head = _repo(tmp_path)
    (repo / "elsewhere.txt").write_text("b\n")
    assert locate(layer).dirty is False
    (layer / "new.yml").write_text("x: 1\n")
    assert locate(layer).dirty is True


def test_a_layer_outside_git_records_nothing(tmp_path):
    assert locate(tmp_path) == Locator(source=None, commit=None, dirty=None)


def test_a_remote_with_credentials_records_no_userinfo(tmp_path):
    _repo_, layer, _head = _repo(tmp_path, origin="https://bot:s3cret@github.com/x/y")
    assert locate(layer).source == "https://github.com/x/y"


def test_a_local_remote_records_no_source(tmp_path):
    _repo_, layer, head = _repo(tmp_path, origin="/home/someone/registry")
    assert locate(layer) == Locator(source=None, commit=head, dirty=False, path="layer")


def test_a_repository_with_no_remote_records_its_commit(tmp_path):
    _repo_, layer, head = _repo(tmp_path, origin=None)
    assert locate(layer) == Locator(source=None, commit=head, dirty=False, path="layer")


def test_locators_are_keyed_by_layer_name(tmp_path):
    _repo_, layer, head = _repo(tmp_path)
    assert locators([layer]) == {"layer": locate(layer)}  # no registry.yml: the folder names it


def test_a_repository_with_no_commits_records_no_commit(tmp_path):
    """Review #1: a freshly `git init`-ed layer has no HEAD. Its files are all untracked, so it
    is dirty, and there is no commit to name."""
    layer = tmp_path / "fresh"
    layer.mkdir()
    (layer / "contract.yml").write_text("id: x\n")
    _git("init", "-q", cwd=layer)
    assert locate(layer) == Locator(source=None, commit=None, dirty=True)


def test_a_sha256_repository_records_its_commit(tmp_path):
    """Review #9: a SHA-256 object-format repository's HEAD is 64 hex digits, and a 40-digit-
    only `CommitSha` crashed `locate`, and with it the build."""
    layer = tmp_path / "sha256"
    layer.mkdir()
    (layer / "contract.yml").write_text("id: x\n")
    _git("init", "-q", "--object-format=sha256", cwd=layer)
    _git("add", ".", cwd=layer)
    _git("commit", "-q", "-m", "one", cwd=layer)
    found = locate(layer)
    assert found.commit is not None and len(found.commit) == 64


def test_a_remote_with_a_token_in_its_query_records_no_source(tmp_path):
    """Review #8: `?private_token=…` is a credential as surely as userinfo is."""
    _repo_, layer, head = _repo(tmp_path, origin="https://gitlab.example.org/x/y?private_token=t")
    assert locate(layer) == Locator(source=None, commit=head, dirty=False, path="layer")


def test_a_layer_at_the_top_of_its_repository_records_no_path(tmp_path):
    """Review #4: the path is left out when the layer is the repository itself."""
    repo, _layer, _head = _repo(tmp_path)
    assert locate(repo).path is None
