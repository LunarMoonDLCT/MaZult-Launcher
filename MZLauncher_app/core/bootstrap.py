"""Bootstrap imports for launcher modules."""
import importlib
import pkgutil

import MZLauncher_app
import MZLauncher_app.core
import MZLauncher_app.gui
import MZLauncher_app.minecraft_account
import MZLauncher_app.modloader
import MZLauncher_app.download
import MZLauncher_app.settings


def preload_modules():
    package = MZLauncher_app
    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        try:
            importlib.import_module(module_info.name)
        except Exception:
            pass
