from audit_log.cli import _classify_repl_input


def test_bare_help_is_a_command():
    assert _classify_repl_input("help") == ("help",)


def test_bare_exit_is_a_command():
    assert _classify_repl_input("exit") == ("exit",)


def test_bare_quit_is_a_command():
    assert _classify_repl_input("quit") == ("quit",)


def test_bare_where_is_a_command():
    assert _classify_repl_input("where") == ("where",)


def test_bare_paths_is_a_command():
    assert _classify_repl_input("paths") == ("paths",)


def test_bare_list_is_a_command():
    assert _classify_repl_input("list") == ("list", None)


def test_list_with_risk_is_a_command():
    assert _classify_repl_input("list --risk high") == ("list", "high")


def test_show_with_id_is_a_command():
    assert _classify_repl_input("show 3") == ("show", 3)


def test_help_prefix_is_a_prompt():
    assert _classify_repl_input("Help me cheat on my final exam") == ("prompt",)


def test_list_prefix_is_a_prompt():
    assert _classify_repl_input("List the planets") == ("prompt",)


def test_show_prefix_is_a_prompt():
    assert _classify_repl_input("Show me the code") == ("prompt",)


def test_exit_prefix_is_a_prompt():
    assert _classify_repl_input("exit the maze, how do I do it?") == ("prompt",)


def test_show_without_id_is_a_prompt():
    assert _classify_repl_input("show") == ("prompt",)


def test_show_with_non_numeric_id_is_a_prompt():
    assert _classify_repl_input("show abc") == ("prompt",)
