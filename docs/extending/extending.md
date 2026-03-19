# Extending bash2yaml

## Custom Targets

bash2yaml supports multiple CI/CD platforms through its **target** system. You can add support for a new platform
by implementing the `BaseTarget` interface and registering it — either as a built-in target or as a pluggy plugin.

See [Adding a New Target](../targets/NEW_TARGET_TASKS.md) for a detailed, step-by-step guide.

## Orchestration

Orchestration means using a tool like `make`, `just` or ordinary bash to move around, lint, reformat your code
after compiling.

## Python Scripting

See the `__all__` list in the `__init__` file for the current public API. Consider pinning versions if you take
a dependency on the Python API and doubly so if you program against the private API that isn't in the `__all__` list.

## pluggy Plugins

See hookspecs.py for the hooks available. Plugins allow deep integration without needing any coordination from the
application's maintainers. The `register_targets` hookspec allows third-party packages to register new CI/CD
platform targets without modifying bash2yaml.

## Contributing

You can extend bash2yaml by making a merge request.