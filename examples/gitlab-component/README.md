# GitLab CI/CD Component example

This example shows bash2yaml compiling a **GitLab CI/CD component template** —
a multi-document YAML file with a `spec:inputs` header, a `---` separator, and
a pipeline body that uses `$[[ inputs.x ]]` interpolation.

bash2yaml never evaluates the interpolation (GitLab does that at `include:`
time). It inlines your `.sh` files into the body while leaving the `spec:`
header and every `$[[ ... ]]` span byte-for-byte intact.

## Layout

```
src/
  scanner/template.yml   # uncompiled component template (spec header + body)
  scripts/scan.sh        # real bash, with IDE/shellcheck support
templates/
  scanner/template.yml   # compiled output — the layout GitLab component repos require
```

## Interpolation inside bash

`src/scripts/scan.sh` uses `$[[ inputs.stage ]]` inside the script. Because
`$[[ ]]` is not valid bash, that usage must be opted into with a pragma:

```bash
# Pragma: gitlab-interpolation
```

The pragma line is stripped from the compiled YAML. Without it, compilation
still passes the tokens through but logs a warning.

## Try it

```bash
./compile.sh
```

Then diff `templates/scanner/template.yml` against `src/scanner/template.yml`:
the `spec:` header is untouched and the `script:` block now contains the
inlined bash.

To scaffold a fresh component repo of your own:

```bash
bash2yaml init --component scanner
```
