"""The builder agent on Run → Console (#511): what the page carries is shortened before it is
stored or sent, and a suggested command is a view the page acts on."""

from mendel_api.agent.console import ConsoleContext, SuggestArgs, shortened, suggest_command


def test_paths_are_cut_to_their_last_two_parts():
    text = (
        "Work dir:\n  /home/someone/projects/runs/abc/work/a4/3e81d2\nreads /data/lab/x/y.fq.gz ok"
    )
    out = shortened(text)
    assert "/home/someone" not in out and "/data/lab" not in out
    assert "…/a4/3e81d2" in out and "…/x/y.fq.gz" in out


def test_a_short_relative_path_is_left_alone():
    assert shortened("cat .command.err and work/a4") == "cat .command.err and work/a4"


def test_the_console_block_is_shortened_and_bounded():
    block = ConsoleContext(run="r1", console="x" * 39000 + " /a/b/c/d.txt", shell="ok").block(3)
    assert block["kind"] == "console" and block["id"] == "console-3"
    assert len(block["console"]) <= 12000 and block["console"].endswith("…/c/d.txt")


def test_a_suggested_command_keeps_whether_it_only_reads():
    view = suggest_command(
        None, SuggestArgs(command="tail  -n 40   .command.err", read_only=True, because="See why.")
    )
    assert view.command == "tail -n 40 .command.err" and view.read_only is True
