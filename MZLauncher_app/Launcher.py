import os
import sys
from pathlib import Path


def _resolve_launcher_core():
    candidates = []
    base_dir = Path(__file__).resolve().parent
    candidates.append(base_dir / 'core' / 'launcher_core.py')
    candidates.append(base_dir.parent / 'core' / 'launcher_core.py')
    candidates.append(Path(sys.executable).resolve().parent / 'core' / 'launcher_core.py')
    if getattr(sys, 'frozen', False):
        meipass = os.environ.get('MEIPASS') or getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.append(Path(meipass) / 'core' / 'launcher_core.py')
            candidates.append(Path(meipass) / 'MZLauncher_app' / 'core' / 'launcher_core.py')
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f'Main launcher core not found. Tried: {", ".join(str(c) for c in candidates)}')


if __name__ == '__main__':
    print("Starting MZLauncher...")
    core_path = _resolve_launcher_core()
    project_root = Path(__file__).resolve().parent.parent
    package_parent = Path(__file__).resolve().parent
    for candidate in [project_root, package_parent, core_path.parent.parent]:
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
    import MZLauncher_app.core.bootstrap as bootstrap
    bootstrap.preload_modules()
    from MZLauncher_app.core.launcher_core import main
    main()
