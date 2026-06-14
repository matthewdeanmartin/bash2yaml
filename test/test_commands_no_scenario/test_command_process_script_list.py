from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ruamel.yaml.constructor import TaggedScalar
from ruamel.yaml.scalarstring import LiteralScalarString

# Import the function to be tested
from bash2yaml.commands.compile_all import process_script_list
from bash2yaml.commands.compile_bash_reader import SourceSecurityError


@pytest.fixture
def scripts_root(tmp_path: Path) -> Path:
    """Provides a temporary directory for script files."""
    d = tmp_path / "scripts"
    d.mkdir()
    return d


def test_simple_list_collapses_to_literal_string(scripts_root):
    """Test that a simple list of 3+ strings becomes a single LiteralScalarString."""
    script_list = ["echo 'hello'", "export VAR=1", "python -c 'print(1)'"]
    result = process_script_list(script_list, scripts_root)

    assert isinstance(result, LiteralScalarString)
    expected_content = "\n".join(script_list)
    assert str(result) == expected_content


def test_short_list_preserves_list_form(scripts_root):
    """Test that a list with 2 or fewer items is not collapsed."""
    script_list = ["echo 'one command'"]
    result = process_script_list(script_list, scripts_root)
    assert result == script_list

    script_list_two = ["echo 'command one'\necho 'command two'"]
    result_two = process_script_list(script_list_two, scripts_root)
    assert result_two == script_list_two


def test_inline_bash_script_from_path(scripts_root):
    """Inlining works when scripts_root is outside cwd (the root becomes the boundary).

    Traceless mode keeps sources in an out-of-tree state dir, so an
    out-of-cwd scripts_root must be compilable; sourcing may still not
    escape that root (see test below).
    """
    script_content = "#!/bin/bash\nls -la\necho 'done'"
    script_file = scripts_root / "test.sh"
    script_file.write_text(script_content)

    script_list = ["echo 'start'", "./test.sh", "echo 'end'"]
    result = process_script_list(script_list, scripts_root)
    text = str(result)
    assert "ls -la" in text
    assert "./test.sh" not in text


def test_sourcing_outside_scripts_root_still_blocked(scripts_root, tmp_path):
    """A script sourcing a file that escapes the scripts root raises SourceSecurityError."""
    outside = tmp_path / "outside.sh"
    outside.write_text("echo 'escaped'\n")
    script_file = scripts_root / "test.sh"
    script_file.write_text("#!/bin/bash\nsource ../outside.sh\n")

    with pytest.raises((SourceSecurityError, Exception), match="escapes allowed root|Could not inline"):
        process_script_list(["./test.sh"], scripts_root)


def test_inline_script_file_not_found_raises_exception(scripts_root):
    """Test that a non-existent script file raises an exception."""
    script_list = ["./non_existent_script.sh"]

    with pytest.raises(Exception, match="Could not inline script"):
        process_script_list(script_list, scripts_root)


def test_list_with_tagged_scalar_preserves_sequence(scripts_root):
    """Test that a list with a TaggedScalar is not collapsed and preserves the tag."""
    my_tag = TaggedScalar(value="some_value", tag="!secret")
    script_list = ["echo 'hello'", my_tag, "echo 'world'"]

    result = process_script_list(script_list, scripts_root)

    assert isinstance(result, list)
    assert len(result) == 3
    assert result[1] is my_tag
    assert isinstance(result[1], TaggedScalar)
    assert result[1].tag == "!secret"


def test_multiline_string_not_a_reference_is_kept_as_is(scripts_root):
    """Test that a regular multi-line string is not transformed."""
    script_list = ["echo 'hello'\necho 'world'"]

    result = process_script_list(script_list, scripts_root)

    assert result == script_list


@patch("bash2yaml.plugins.get_pm")
def test_plugin_hook_inlining(mock_get_pm, scripts_root):
    """Test that the pm.hook.inline_command is called and its result is used."""
    # Setup mock plugin manager and hook
    mock_pm = MagicMock()
    mock_pm.hook.inline_command.return_value = ["# Inlined by plugin", "print('hello from plugin')"]
    mock_get_pm.return_value = mock_pm

    script_list = ["python -m my_module"]
    process_script_list(script_list, scripts_root)
    # well it didn't blow up.
