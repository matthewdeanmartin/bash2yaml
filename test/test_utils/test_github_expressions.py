"""Unit tests for GitHub Actions ``${{ ... }}`` expression support."""

from __future__ import annotations

import logging

from bash2yaml.utils.github_expressions import EXPRESSION_REGEX, contains_expression, strip_expression_pragma_lines


class TestExpressionRegex:
    def test_matches_simple_input(self):
        assert EXPRESSION_REGEX.search("echo ${{ inputs.environment }}")

    def test_matches_function_call(self):
        assert EXPRESSION_REGEX.search("${{ contains(github.ref, 'release') }}")

    def test_matches_two_on_one_line_separately(self):
        line = "echo ${{ inputs.a }} and ${{ inputs.b }}"
        assert len(EXPRESSION_REGEX.findall(line)) == 2

    def test_no_match_on_plain_bash_braces(self):
        assert not EXPRESSION_REGEX.search('echo "${VAR}" and ${OTHER:-x}')

    def test_no_match_on_gitlab_interpolation(self):
        assert not EXPRESSION_REGEX.search("echo $[[ inputs.stage ]]")


class TestContainsExpression:
    def test_true(self):
        assert contains_expression("x=${{ github.sha }}")

    def test_false(self):
        assert not contains_expression("x=$GITHUB_SHA")


class TestStripExpressionPragmaLines:
    def test_pragma_line_stripped(self):
        content = "#!/bin/bash\n# Pragma: github-expression\necho ${{ inputs.x }}\n"
        result = strip_expression_pragma_lines(content, "test.sh")
        assert "github-expression" not in result
        assert "echo ${{ inputs.x }}" in result

    def test_pragma_case_insensitive(self):
        content = "# pragma: GitHub-Expression\necho hi\n"
        result = strip_expression_pragma_lines(content, "test.sh")
        assert "pragma" not in result.lower()

    def test_no_pragma_content_unchanged(self):
        content = "echo plain\n"
        assert strip_expression_pragma_lines(content, "test.sh") == content

    def test_expression_without_pragma_warns(self, caplog):
        content = "echo ${{ inputs.x }}\n"
        with caplog.at_level(logging.WARNING):
            result = strip_expression_pragma_lines(content, "test.sh")
        assert result == content
        assert any("github-expression" in r.message for r in caplog.records)

    def test_expression_with_pragma_does_not_warn(self, caplog):
        content = "# Pragma: github-expression\necho ${{ inputs.x }}\n"
        with caplog.at_level(logging.WARNING):
            strip_expression_pragma_lines(content, "test.sh")
        assert not caplog.records
