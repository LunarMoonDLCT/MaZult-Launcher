import os
import sys
from pathlib import Path
import datetime
import logging


if __name__ == '__main__':
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Starting MZLauncher...")


    logging.info("Starting MZLauncher...")
    project_root = Path(__file__).resolve().parent.parent
    package_dir = Path(__file__).resolve().parent
    for candidate in [str(project_root), str(package_dir)]:
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    from MZLauncher_app.core.splash import main
    main()
