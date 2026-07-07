import os
import sys
from pathlib import Path


if __name__ == '__main__':
    print("Starting MZLauncher...")
    project_root = Path(__file__).resolve().parent.parent
    package_dir = Path(__file__).resolve().parent
    for candidate in [str(project_root), str(package_dir)]:
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    from MZLauncher_app.core.launcher_core import main
    main()
