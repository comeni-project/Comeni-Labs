"""A tag resolved to the digest a run pulls (#308), against recorded registry responses."""

import pytest
from comeni_vendor.images import ImageError, digest_of_image

DIGEST = "sha256:" + "a" * 64
WAVE = "community.wave.seqera.io/library/htslib_samtools:1.24--d697cfb9dce007cd"
CHALLENGE = ('Bearer realm="https://cerbero.seqera.io/auth/token",'
             'service="community.wave.seqera.io",scope="repository:library/htslib_samtools:pull"')


class Recorded:
    """What a registry answered, keyed by URL; the requests made, in order."""

    def __init__(self, answers):
        self.answers, self.asked = answers, []

    def __call__(self, url, headers):
        self.asked.append((url, headers))
        return self.answers[url]


def test_an_open_registry_answers_with_the_digest():
    url = "https://quay.io/v2/biocontainers/fastqc/manifests/0.12.1--hdfd78af_0"
    http = Recorded({url: (200, {"docker-content-digest": DIGEST}, b"")})
    assert digest_of_image("quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0", http=http) == DIGEST
    (_, headers), = http.asked
    assert "application/vnd.oci.image.index.v1+json" in headers["Accept"]


def test_a_token_challenge_is_answered_once_anonymously():
    manifest = ("https://community.wave.seqera.io/v2/library/htslib_samtools/manifests/"
                "1.24--d697cfb9dce007cd")
    token = ("https://cerbero.seqera.io/auth/token?service=community.wave.seqera.io"
             "&scope=repository%3Alibrary%2Fhtslib_samtools%3Apull")
    answers = {manifest: (401, {"www-authenticate": CHALLENGE}, b""),
               token: (200, {}, b'{"token": "t0k"}')}

    def http(url, headers):
        if url == manifest and headers.get("Authorization") == "Bearer t0k":
            return 200, {"docker-content-digest": DIGEST}, b""
        return answers[url]

    assert digest_of_image(WAVE, http=http) == DIGEST


def test_a_pinned_reference_is_kept_as_it_is_without_asking():
    http = Recorded({})
    assert digest_of_image(f"{WAVE}@{DIGEST}", http=http) == DIGEST and http.asked == []


@pytest.mark.parametrize("answer", [(404, {}, b""), (200, {}, b""),
                                    (200, {"docker-content-digest": "sha256:short"}, b"")])
def test_a_registry_that_gives_no_digest_is_an_error_naming_the_image(answer):
    url = "https://quay.io/v2/a/b/manifests/1"
    with pytest.raises(ImageError, match="quay.io/a/b:1"):
        digest_of_image("quay.io/a/b:1", http=Recorded({url: answer}))


def test_an_image_with_no_tag_is_refused_rather_than_guessed_latest():
    with pytest.raises(ImageError, match="no tag"):
        digest_of_image("quay.io/a/b", http=Recorded({}))


CONTRACT = """declares: contract
id: nf-core/x@1.0
# a comment that must survive
container: quay.io/a/b:1
provenance: {source: hand}
"""


def _registry(tmp_path, text=CONTRACT):
    contract = tmp_path / "tools/nf-core/x/contract.yml"
    contract.parent.mkdir(parents=True)
    contract.write_text(text)
    return contract


def test_pinning_rewrites_only_the_container_line(tmp_path):
    from comeni_vendor.images import pin_containers

    contract = _registry(tmp_path)
    url = "https://quay.io/v2/a/b/manifests/1"
    http = Recorded({url: (200, {"docker-content-digest": DIGEST}, b"")})
    changed = pin_containers(tmp_path, http=http)
    assert changed == [(contract, "quay.io/a/b:1", f"quay.io/a/b:1@{DIGEST}")]
    assert contract.read_text() == CONTRACT.replace("quay.io/a/b:1", f"quay.io/a/b:1@{DIGEST}")


def test_pinning_a_pinned_registry_changes_nothing_and_asks_nobody(tmp_path):
    from comeni_vendor.images import pin_containers

    contract = _registry(tmp_path, CONTRACT.replace("quay.io/a/b:1", f"quay.io/a/b:1@{DIGEST}"))
    before = contract.read_text()
    http = Recorded({})
    assert pin_containers(tmp_path, http=http) == [] and http.asked == []
    assert contract.read_text() == before


def test_one_image_that_cannot_be_resolved_stops_before_any_file_is_written(tmp_path):
    from comeni_vendor.images import pin_containers

    good = _registry(tmp_path)
    other = tmp_path / "tools/nf-core/y/contract.yml"
    other.parent.mkdir(parents=True)
    other.write_text(CONTRACT.replace("quay.io/a/b:1", "quay.io/a/c:2"))
    answers = {"https://quay.io/v2/a/b/manifests/1": (200, {"docker-content-digest": DIGEST}, b""),
               "https://quay.io/v2/a/c/manifests/2": (404, {}, b"")}
    with pytest.raises(ImageError, match="quay.io/a/c:2"):
        pin_containers(tmp_path, http=Recorded(answers))
    assert good.read_text() == CONTRACT


def test_the_command_pins_and_says_what_it_pinned(tmp_path, monkeypatch, capsys):
    from comeni_vendor import images
    from comeni_vendor.cli import main

    _registry(tmp_path)
    url = "https://quay.io/v2/a/b/manifests/1"
    monkeypatch.setattr(images, "_urllib", Recorded({url: (200, {"docker-content-digest": DIGEST},
                                                          b"")}))
    assert main(["pin-containers", "--registry", str(tmp_path)]) == 0
    assert "1 contract(s) pinned" in capsys.readouterr().out
