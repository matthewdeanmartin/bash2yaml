import os
from unittest import mock

from bash2yaml.utils.update_checker import _Color, can_use_color, check_for_updates, reset_cache


@mock.patch("bash2yaml.utils.update_checker.fetch_json")
def test_finds_newer_version(mock_fetch):
    """Test that a known old version returns an update message string."""
    mock_fetch.return_value = {
        "info": {"version": "2.28.0"},
        "releases": {"2.28.0": [{"yanked": False}], "2.0.0": [{"yanked": False}]},
    }
    reset_cache("requests")
    result = check_for_updates(package_name="requests", current_version="2.0.0")
    assert result is not None
    assert "A new stable version of requests is available" in result
    assert "you are using 2.0.0" in result


@mock.patch("bash2yaml.utils.update_checker.fetch_json")
def test_handles_up_to_date_package(mock_fetch):
    """Test that a version that is clearly too high results in None."""
    mock_fetch.return_value = {
        "info": {"version": "1.0.0"},
        "releases": {"1.0.0": [{"yanked": False}]},
    }
    reset_cache("packaging")
    result = check_for_updates(package_name="packaging", current_version="999.0.0")
    assert result is None


@mock.patch("bash2yaml.utils.update_checker.fetch_json")
def test_prerelease_check_finds_newer(mock_fetch):
    """Test that pre-releases are found when the flag is enabled."""
    mock_fetch.return_value = {
        "info": {"version": "2.1.0a1"},
        "releases": {"2.0.0": [{"yanked": False}], "2.1.0a1": [{"yanked": False}]},
    }
    reset_cache("pandas")
    result = check_for_updates(package_name="pandas", current_version="2.0.0", include_prereleases=True)
    assert result is not None
    assert "A new stable version of pandas is available" in result
    assert "2.1.0a1" in result


@mock.patch("bash2yaml.utils.update_checker.fetch_json")
@mock.patch("bash2yaml.utils.update_checker.can_use_color", return_value=True)
def test_color_output_enabled(mock_color, mock_fetch):
    """Test that ANSI color codes are present when color is enabled."""
    mock_fetch.return_value = {
        "info": {"version": "2.28.0"},
        "releases": {"2.28.0": [{"yanked": False}], "2.0.0": [{"yanked": False}]},
    }
    reset_cache("requests")
    result = check_for_updates(package_name="requests", current_version="2.0.0")
    assert result is not None
    c = _Color()
    assert c.YELLOW in result, "Output should contain color codes when enabled"


@mock.patch("bash2yaml.utils.update_checker.fetch_json")
@mock.patch.dict(os.environ, {"CI": "true"})
def test_color_output_disabled_in_ci(mock_fetch):
    """Test that color is disabled when a CI environment variable is set."""
    mock_fetch.return_value = {
        "info": {"version": "1.0.0"},
        "releases": {"1.0.0": [{"yanked": False}], "0.1.0": [{"yanked": False}]},
    }
    reset_cache("httpx")
    assert not can_use_color()
    result = check_for_updates(package_name="httpx", current_version="0.1.0")
    assert result is not None
    c = _Color()
    assert c.YELLOW not in result, "Output should not have color in CI"
