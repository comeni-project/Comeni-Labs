"""Validation and serialization contracts for registry-layer repository coordinates."""

import pytest
from comeni_core.artifact.lockfile import Locator, LockedLayer
from comeni_core.spell.marks import CommitSha, RepoUrl
from pydantic import TypeAdapter, ValidationError

URL = TypeAdapter(RepoUrl)
SHA = TypeAdapter(CommitSha)


@pytest.mark.parametrize("url", ["https://github.com/comeni-project/comeni-registry",
                                 "ssh://git@example.org/lab/registry.git",
                                 "git@github.com:comeni-project/comeni-registry.git"])
def test_a_network_url_is_a_source(url):
    assert URL.validate_python(url) == url


@pytest.mark.parametrize("url", ["https://bot:s3cret@github.com/x/y", "https://token@github.com/x/y",
                                 "ssh://git:pw@example.org/x", "/home/someone/registry",
                                 "file:///home/someone/registry", "registry", "http://host/a b",
                                 "https://host/r?private_token=abc", "https://host/r#frag",
                                 "git@host:r?token=abc"])
def test_repo_url_refuses_userinfo_and_paths(url):
    with pytest.raises(ValidationError):
        URL.validate_python(url)


def test_a_commit_is_forty_lowercase_hex():
    assert SHA.validate_python("a" * 40) == "a" * 40
    for bad in ("a" * 39, "A" * 40, "g" * 40):
        with pytest.raises(ValidationError):
            SHA.validate_python(bad)


def test_an_unlocated_layer_dumps_as_before():
    """Unknown repository coordinates stay out of the serialized layer record."""
    layer = LockedLayer(name="comeni-registry", digest="sha256:" + "0" * 64)
    assert layer.model_dump(mode="json") == {"name": "comeni-registry",
                                             "digest": "sha256:" + "0" * 64}


def test_a_located_layer_carries_its_locator():
    found = Locator(source="https://github.com/x/y", commit="b" * 40, dirty=False)
    layer = LockedLayer(name="x", digest="sha256:" + "0" * 64, **found.model_dump())
    assert layer.model_dump(mode="json")["commit"] == "b" * 40
    assert layer.model_dump(mode="json")["dirty"] is False


def test_a_sha256_commit_is_sixty_four_lowercase_hex():
    assert SHA.validate_python("d" * 64) == "d" * 64
    with pytest.raises(ValidationError):
        SHA.validate_python("d" * 50)


def test_a_layer_path_is_inside_its_repository():
    """A layer path is repository-relative and cannot name a local machine path."""
    from comeni_core.spell.marks import RepoPath

    path = TypeAdapter(RepoPath)
    assert path.validate_python("registry/layer") == "registry/layer"
    for bad in ("/home/someone/registry", "../elsewhere", "~/registry"):
        with pytest.raises(ValidationError):
            path.validate_python(bad)
