"""Metadata for bash2yaml."""

__all__ = [
    "__credits__",
    "__dependencies__",
    "__description__",
    "__keywords__",
    "__license__",
    "__readme__",
    "__requires_python__",
    "__status__",
    "__title__",
    "__version__",
]

__title__ = "bash2yaml"
__version__ = "0.11.1"
__description__ = "Compile bash to pipeline yaml- Gitlab, GitHub and more"
__readme__ = "README.md"
__credits__ = [{"name": "Matthew Martin", "email": "matthewdeanmartin@gmail.com"}]
__keywords__ = ["bash", "gitlab", "github"]
__license__ = "MIT"
__requires_python__ = ">=3.11"
__dependencies__ = [
    "ruamel.yaml>=0.18.14",
    "jsonschema>=4.23.0",
    "importlib_resources>=6.4.5",
    "toml>=0.10.2",
    "do_i_need_to_upgrade>=0.1.0",
    "urllib3>=2.0.0",
    "certifi>=2025.8.3",
    "python-gitlab>=1.0.0",
]
__status__ = "5 - Production/Stable"
