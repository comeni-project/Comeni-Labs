"""The installation's own layer is local (#462 review I5): never located through a repository
that happens to enclose it, which would record a public origin that cannot hold it."""

import subprocess

from mendel_compiler.locate import INSTALLATION_FILE, locate


def test_an_installation_layer_inside_a_checkout_has_no_source(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin",
                    "https://github.com/x/y.git"], check=True)
    layer = tmp_path / "workspace" / "layer"
    layer.mkdir(parents=True)
    (layer / "registry.yml").write_text("name: installation\nrequires_format: 2\n")
    (layer / INSTALLATION_FILE).write_text("This installation's own layer.\n")
    found = locate(layer)
    assert found.source is None and found.commit is None and found.path is None
