"""Unit tests for GitLab CI/CD component template support (spec:inputs)."""

from __future__ import annotations

import logging

from bash2yaml.utils.gitlab_components import (
    contains_interpolation,
    find_component_templates,
    is_component_template,
    split_component_template,
    strip_interpolation_pragma_lines,
    validate_spec_header,
)

COMPONENT = """# a leading comment
spec:
  inputs:
    stage:
      default: test
    job-prefix:
      type: string
---
"$[[ inputs.job-prefix ]]-scan":
  stage: $[[ inputs.stage ]]
  script:
    - ./scripts/scan.sh
"""


class TestSplitComponentTemplate:
    def test_split_and_reassemble_is_byte_identical(self):
        component = split_component_template(COMPONENT)
        assert component is not None
        assert component.reassemble() == COMPONENT
        assert component.separator == "---\n"
        assert component.header.startswith("# a leading comment")
        assert component.body.startswith('"$[[ inputs.job-prefix ]]-scan":')

    def test_reassemble_with_new_body(self):
        component = split_component_template(COMPONENT)
        assert component is not None
        rebuilt = component.reassemble("job:\n  script: [echo hi]\n")
        assert rebuilt.startswith(component.header)
        assert rebuilt.endswith("job:\n  script: [echo hi]\n")

    def test_plain_pipeline_is_not_a_component(self):
        assert split_component_template("job:\n  script:\n    - echo hi\n") is None

    def test_multi_doc_without_spec_is_not_a_component(self):
        assert split_component_template("foo: bar\n---\nbaz: 1\n") is None

    def test_explicit_document_start_before_spec(self):
        text = "---\nspec:\n  inputs:\n    a:\n---\nbody: 1\n"
        component = split_component_template(text)
        assert component is not None
        assert component.body == "body: 1\n"
        assert component.reassemble() == text

    def test_indented_dashes_are_not_a_separator(self):
        text = 'spec:\n  inputs:\n    a:\n      default: |\n        ---\n        not a separator\n---\njob:\n  script: ["echo hi"]\n'
        component = split_component_template(text)
        assert component is not None
        assert component.body == 'job:\n  script: ["echo hi"]\n'

    def test_is_component_template(self):
        assert is_component_template(COMPONENT)
        assert not is_component_template("a: 1\n")


class TestValidateSpecHeader:
    def test_valid_header(self):
        component = split_component_template(COMPONENT)
        assert component is not None
        ok, errors = validate_spec_header(component.header)
        assert ok, errors

    def test_inputs_with_no_options_are_valid(self):
        ok, errors = validate_spec_header("spec:\n  inputs:\n    bare:\n")
        assert ok, errors

    def test_unknown_input_option_is_an_error(self):
        ok, errors = validate_spec_header("spec:\n  inputs:\n    x:\n      typ: string\n")
        assert not ok
        assert "unknown option" in errors[0]

    def test_invalid_type_is_an_error(self):
        ok, errors = validate_spec_header("spec:\n  inputs:\n    x:\n      type: integer\n")
        assert not ok
        assert "invalid type" in errors[0]

    def test_options_must_be_a_list(self):
        ok, errors = validate_spec_header("spec:\n  inputs:\n    x:\n      options: nope\n")
        assert not ok
        assert "'options' must be a list" in errors[0]

    def test_unknown_spec_key_is_an_error(self):
        ok, errors = validate_spec_header("spec:\n  imputs:\n    x:\n")
        assert not ok
        assert "unknown keys" in errors[0]


class TestInterpolationPragma:
    def test_pragma_line_is_stripped(self):
        content = "#!/bin/bash\n# Pragma: gitlab-interpolation\necho $[[ inputs.stage ]]\n"
        result = strip_interpolation_pragma_lines(content, "scan.sh")
        assert "Pragma" not in result
        assert "$[[ inputs.stage ]]" in result

    def test_interpolation_without_pragma_warns_but_passes_through(self, caplog):
        content = "echo $[[ inputs.stage ]]\n"
        with caplog.at_level(logging.WARNING):
            result = strip_interpolation_pragma_lines(content, "scan.sh")
        assert result == content
        assert any("gitlab-interpolation" in r.message for r in caplog.records)

    def test_plain_script_untouched_and_silent(self, caplog):
        content = "echo hello\n"
        with caplog.at_level(logging.WARNING):
            result = strip_interpolation_pragma_lines(content, "x.sh")
        assert result == content
        assert not caplog.records

    def test_contains_interpolation(self):
        assert contains_interpolation("a $[[ inputs.x ]] b")
        assert contains_interpolation("$[[ inputs.x | expand_vars ]]")
        assert not contains_interpolation("plain $X and ${Y}")


class TestFindComponentTemplates:
    def test_finds_only_component_files(self, tmp_path):
        (tmp_path / "templates").mkdir()
        (tmp_path / "templates" / "comp.yml").write_text(COMPONENT, encoding="utf-8")
        (tmp_path / "plain.yml").write_text("job:\n  script: [echo]\n", encoding="utf-8")
        found = find_component_templates(tmp_path)
        assert [p.name for p in found] == ["comp.yml"]

    def test_missing_dir_is_empty(self, tmp_path):
        assert find_component_templates(tmp_path / "nope") == []
