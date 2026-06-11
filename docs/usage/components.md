# GitLab CI/CD Components (`spec:inputs`)

GitLab's [CI/CD components](https://docs.gitlab.com/ee/ci/components/) are the
blessed way to publish reusable pipeline configuration. A component template
is a *multi-document* YAML file: a `spec:` header document declaring inputs, a
`---` separator, then the pipeline body. Consumers set the inputs via
`include: component:`, and GitLab substitutes `$[[ inputs.x ]]` interpolation
spans at include time.

bash2yaml compiles component templates the same way it compiles any other
GitLab CI file, with three guarantees:

1. **The `spec:` header round-trips byte-for-byte.** It is split off as raw
   text before compilation and reattached unchanged — never parsed and
   re-dumped.
2. **Interpolation is opaque.** `$[[ inputs.x ]]` (including function syntax
   like `$[[ inputs.x | expand_vars ]]`) is never split, re-quoted, or
   evaluated, whether it appears in keys, values, or script lines.
3. **Validation understands the split.** The body is validated against the
   GitLab CI schema; the header is validated against the `spec:inputs` shape
   (allowed input options: `default`, `description`, `type`, `options`,
   `regex`; allowed types: `string`, `number`, `boolean`, `array`). Typos
   fail at compile time instead of at include time.

## Example

`src/scanner/template.yml`:

```yaml
spec:
  inputs:
    stage:
      default: test
    job-prefix:
      type: string
      default: "secret"
---
"$[[ inputs.job-prefix ]]-scan":
  stage: $[[ inputs.stage ]]
  script:
    - ./scripts/scan.sh
```

Run `bash2yaml compile --in src --out templates` and the compiled
`templates/scanner/template.yml` keeps the header and job structure intact,
with `scan.sh` inlined into the `script:` block. The `templates/<name>/template.yml`
output layout is exactly what GitLab requires of a components repo.

## Interpolation inside bash scripts

`$[[ ]]` is not valid bash, so using GitLab interpolation inside a `.sh`
source file is opt-in via a pragma:

```bash
#!/usr/bin/env bash
# Pragma: gitlab-interpolation
set -euo pipefail

echo "Scanning during the $[[ inputs.stage ]] stage"
```

The pragma line is stripped from the compiled YAML. If a script contains
`$[[ ]]` without the pragma, the tokens still pass through verbatim but
bash2yaml logs a warning, since shellcheck and bash will both reject the
script as written. Conversely, `bash2yaml decompile` adds the pragma
automatically when it extracts script lines containing interpolation.

## Scaffolding a component repo

```bash
bash2yaml init --component scanner
```

creates `src/scanner/template.yml` (with a `spec:inputs` header),
`src/scripts/scanner.sh`, and a `[tool.bash2yaml]` config with
`input_dir = "src"` / `output_dir = "templates"`.

`bash2yaml doctor` reports detected component templates in the input
directory, and `decompile` preserves `spec:` headers when extracting scripts
from an existing component repo.

A complete worked example lives in
[`examples/gitlab-component/`](https://github.com/matthewdeanmartin/bash2yaml/tree/main/examples/gitlab-component).
