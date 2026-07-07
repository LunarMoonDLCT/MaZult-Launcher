import runpy
import sys
from pathlib import Path

if __name__ == '__main__':
    print("Starting MZLauncher...")
    core_script = Path(__file__).resolve().parent / 'core' / 'launcher_core.py'
    if not core_script.exists():
        raise FileNotFoundError(f'Main launcher core not found: {core_script}')
    runpy.run_path(str(core_script), run_name='__main__')
    sys.exit(0)
