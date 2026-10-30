"""Cutting a release: only a green main, only a new version, only once. A fake GitHub."""

import httpx
import pytest
import sqlalchemy as sa
from comeni_flow.interpret import Refused
from mendel_api.db import session_scope
from mendel_api.models import ForgeRelease
from mendel_api.services import forge_releases
from mendel_api.services.github_publisher import GitHubPublisher
from mendel_api_tests.database import reachable
from mendel_forge.publishing import PublishUnavailable
from mendel_forge.releases import Fragment, Release, Unreleased

pytestmark = pytest.mark.skipif(not reachable(), reason="no database")

GREEN = Unreleased(last="v0.4.0", commit="c1", ahead=2, checks="green",
                   fragments=[Fragment(path="changelog.d/a.md", text="- `a`: added.\n")])


class FakeSource:
    def __init__(self, now=GREEN):
        self.now = now
        self.published = [Release(tag="v0.4.0")]

    def unreleased(self):
        return self.now

    def releases(self):
        return self.published


class FakePublisher:
    def __init__(self):
        self.cut, self.refuse = [], False

    def cut_release(self, version, notes, commit):
        if self.refuse:
            raise PublishUnavailable("GitHub refused POST: 422")
        self.cut.append((version, notes, commit))
        return Release(tag=version, notes=notes)


@pytest.fixture
def fakes(monkeypatch):
    with session_scope() as db:
        db.execute(sa.text("DELETE FROM forge_release"))
    source, publisher = FakeSource(), FakePublisher()
    monkeypatch.setenv("COMENI_FORGE_GITHUB_TOKEN_SET", "set")
    monkeypatch.setattr(forge_releases, "source", lambda: source)
    monkeypatch.setattr(forge_releases, "publisher", lambda: publisher)

    async def queued(*args, **kwargs):
        return True

    monkeypatch.setattr(forge_releases.jobs, "enqueue", queued)
    forge_releases.forget()
    return source, publisher


def test_the_page_suggests_the_next_version_and_notes(fakes):
    page = forge_releases.overview()
    assert page.suggested == "v0.5.0" and "`a`: added." in page.notes
    assert page.unreleased.ahead == 2 and page.unavailable is None


@pytest.mark.asyncio
@pytest.mark.parametrize("version", ["v0.4.0", "v0.3.9", "0.5.0", "v0.5", "latest"])
async def test_a_version_must_be_well_formed_and_newer(fakes, version):
    with pytest.raises(Refused, match="MF0519"):
        await forge_releases.start(version, "notes", "rafael")


@pytest.mark.asyncio
async def test_nothing_to_release_is_refused(fakes):
    fakes[0].now = GREEN.model_copy(update={"ahead": 0})
    forge_releases.forget()
    with pytest.raises(Refused, match="MF0519.*nothing"):
        await forge_releases.start("v0.5.0", "notes", "rafael")


@pytest.mark.asyncio
async def test_a_main_that_is_not_green_is_refused(fakes):
    fakes[0].now = GREEN.model_copy(update={"checks": "red", "says": "failed: lint"})
    forge_releases.forget()
    with pytest.raises(Refused, match="MF0519.*failed: lint"):
        await forge_releases.start("v0.5.0", "notes", "rafael")


@pytest.mark.asyncio
async def test_a_main_gone_red_is_refused_at_the_job(fakes):
    await forge_releases.start("v0.5.0", "notes", "rafael")
    fakes[0].now = GREEN.model_copy(update={"checks": "red", "says": "failed: lint"})
    forge_releases.cut("v0.5.0")
    assert not fakes[1].cut
    row = forge_releases.overview().recent[0]
    assert row.state == "failed" and "failed: lint" in row.says


@pytest.mark.asyncio
async def test_cutting_names_the_commit_it_read_and_who(fakes):
    await forge_releases.start("v0.5.0", "the notes", "rafael")
    fakes[0].now = GREEN.model_copy(update={"commit": "c2"})
    forge_releases.cut("v0.5.0")
    assert fakes[1].cut == [("v0.5.0", "the notes", "c2")]
    row = forge_releases.overview().recent[0]
    assert row.state == "done" and row.commit == "c2" and row.cut_by == "rafael"


@pytest.mark.asyncio
async def test_two_cuts_make_one_release(fakes):
    await forge_releases.start("v0.5.0", "notes", "rafael")
    with pytest.raises(Refused, match="MF0519"):
        await forge_releases.start("v0.6.0", "notes", "ana")


def test_the_database_holds_one_cut_in_progress_at_most(fakes):
    row = dict(notes="n", state="cutting", cut_by="r", cut_at=sa.func.now())
    with session_scope() as db:
        db.add(ForgeRelease(version="v1.0.0", **row))
    with pytest.raises(sa.exc.IntegrityError), session_scope() as db:
        db.add(ForgeRelease(version="v2.0.0", **row))


@pytest.mark.asyncio
async def test_github_refusing_says_so_and_frees_the_next_attempt(fakes):
    fakes[1].refuse = True
    await forge_releases.start("v0.5.0", "notes", "rafael")
    forge_releases.cut("v0.5.0")
    assert "422" in forge_releases.overview().recent[0].says
    fakes[1].refuse = False
    await forge_releases.start("v0.5.0", "notes", "rafael")
    forge_releases.cut("v0.5.0")
    assert fakes[1].cut


@pytest.mark.asyncio
async def test_no_token_says_why(fakes, monkeypatch):
    monkeypatch.delenv("COMENI_FORGE_GITHUB_TOKEN_SET")
    assert "MF0516" in forge_releases.overview().unavailable
    with pytest.raises(Refused, match="MF0516"):
        await forge_releases.start("v0.5.0", "notes", "rafael")


def test_github_unreadable_still_draws_the_page(fakes, monkeypatch):
    def down():
        from mendel_forge.releases import ReleaseUnavailable
        raise ReleaseUnavailable("GitHub could not be reached: ConnectError")

    monkeypatch.setattr(forge_releases, "source", lambda: type(
        "Down", (), {"unreleased": staticmethod(down), "releases": staticmethod(down)})())
    forge_releases.forget()
    page = forge_releases.overview()
    assert page.unreleased is None and "could not be reached" in page.problem


def test_the_publisher_tags_the_commit_it_was_given(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(201, json={"tag_name": "v0.5.0", "body": "n"})

    publisher = GitHubPublisher("x/y", "t", tmp_path,
                                client=httpx.Client(transport=httpx.MockTransport(handler)))
    released = publisher.cut_release("v0.5.0", "n", "abc")
    assert released.tag == "v0.5.0" and seen[0].url.path == "/repos/x/y/releases"
    assert b'"target_commitish":"abc"' in seen[0].content.replace(b" ", b"")
