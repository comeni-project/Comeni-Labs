"""A module's tool version is the conda package that is its tool (forge spec §2, #407)."""

from mendel_forge.model import CondaPackage
from mendel_forge.versions import parse_packages, same_name, tool_version


def _pkg(name: str, version: str) -> CondaPackage:
    return CondaPackage(channel="bioconda", name=name, version=version)


def test_trimgalore_matches_trim_galore():
    assert same_name("trimgalore", "trim-galore")
    assert tool_version([_pkg("trim-galore", "0.6.10")], "trimgalore", []) == "0.6.10"


def test_the_tool_not_the_first_package():
    packages = [_pkg("htslib", "1.21"), _pkg("samtools", "1.21"), _pkg("star", "2.7.11b")]
    assert tool_version(packages, "star/align", []) == "2.7.11b"


def test_falls_back_to_the_meta_tool_name():
    packages = [_pkg("baz", "1.0"), _pkg("htslib", "1.21")]
    assert tool_version(packages, "foo/bar", ["baz"]) == "1.0"


def test_several_matches_is_unknown():
    packages = [_pkg("bwa", "0.7.19"), _pkg("BWA", "0.7.18")]
    assert tool_version(packages, "bwa/mem", []) is None


def test_no_match_is_unknown_not_a_guess():
    assert tool_version([_pkg("bar", "1.0")], "foo", []) is None


def test_parse_packages_reads_channel_name_and_version():
    environment = (
        "channels: [conda-forge, bioconda]\n"
        "dependencies:\n  - bioconda::star=2.7.11b\n  - pigz=2.8\n"
    )
    assert parse_packages(environment) == [_pkg("star", "2.7.11b"),
                                           CondaPackage(channel=None, name="pigz", version="2.8")]


def test_a_language_ecosystem_prefix_is_not_part_of_the_name():
    """conda names an R package `r-ampir` and a Bioconductor one `bioconductor-affy`."""
    assert tool_version([_pkg("r-ampir", "1.1.0"), _pkg("r-base", "4.4")], "ampir", []) == "1.1.0"
    assert tool_version([_pkg("bioconductor-affy", "1.84.0")], "affy/justrma", []) == "1.84.0"
    assert tool_version([_pkg("ncbi-amrfinderplus", "4.0.3")], "amrfinderplus/run", []) == "4.0.3"
