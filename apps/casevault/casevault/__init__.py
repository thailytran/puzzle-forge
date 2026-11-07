"""Case Vault website (docs/CASEVAULT.md). Never imports `forge`."""

import os
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("casevault")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
GIT_SHA = os.environ.get("CASEVAULT_GIT_SHA", "")[:7]
