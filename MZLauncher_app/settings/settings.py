import json
import os
import sys
from pathlib import Path


def get_appdata_path():
    if sys.platform.startswith('win32'):
        return Path(os.getenv('APPDATA')) / '.mazultlauncher'
    elif sys.platform.startswith('linux'):
        return Path.home() / '.mazultlauncher'
    elif sys.platform.startswith('darwin'):
        return Path.home() / 'Library' / 'Application Support' / '.mazultlauncher'
    return Path.home() / '.mazultlauncher'


ACCOUNTS_FILE = get_appdata_path() / 'users.json'
SETTINGS_FILE = get_appdata_path() / 'settings.json'
VERSION_FILE = get_appdata_path() / 'versions.json'


def load_accounts():
    os.makedirs(get_appdata_path(), exist_ok=True)
    if ACCOUNTS_FILE.exists():
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf8') as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError('users.json is not a list')
            for i, acc in enumerate(data):
                if not isinstance(acc, dict):
                    raise ValueError(f'Invalid user entry at {i}')
                if 'type' not in acc or 'name' not in acc:
                    raise ValueError(f'Missing keys in user entry at {i}')
            return data
        except Exception as e:
            print(f'[ERR] users.json is broken: {e}. Resetting file...')
            try:
                with open(ACCOUNTS_FILE, 'w', encoding='utf8') as f:
                    json.dump([], f, indent=4)
            except Exception as write_err:
                print(f'[FATAL] Could not reset users.json: {write_err}')
            return []

    with open(ACCOUNTS_FILE, 'w', encoding='utf8') as f:
        json.dump([], f, indent=4)
    return []


def save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w', encoding='utf8') as f:
        json.dump(accounts, f, indent=4)


def save_settings(username=None, version_id=None, ram_mb=None, mc_dir=None, filters=None, dev_console=None,
                  hide_on_launch=None, jvm_args=None, discord_rpc=None, language=None, java_mode=None,
                  java_path=None, skip_version_check=None):
    data = load_settings()
    if username is not None:
        data['username'] = username
    if version_id is not None:
        data['version_id'] = version_id
    if ram_mb is not None:
        data['ram_mb'] = ram_mb
    if mc_dir is not None:
        data['minecraft_directory'] = str(mc_dir)
    if filters is not None:
        data['filters'] = filters
    if dev_console is not None:
        data['dev_console'] = dev_console
    if hide_on_launch is not None:
        data['hide_on_launch'] = hide_on_launch
    if jvm_args is not None:
        data['jvm_args'] = jvm_args
    if discord_rpc is not None:
        data['discord_rpc'] = discord_rpc
    if language is not None:
        data['language'] = language
    if java_mode is not None:
        data['java_mode'] = java_mode
    if java_path is not None:
        data['java_path'] = java_path
    if skip_version_check is not None:
        data['skip_version_check'] = skip_version_check

    os.makedirs(get_appdata_path(), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf8') as f:
        json.dump(data, f, indent=4)


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        'filters': {
            'release': True,
            'snapshot': False,
            'beta': False,
            'alpha': False,
            'installed': True,
        },
        'dev_console': False,
        'hide_on_launch': True,
        'jvm_args': [],
        'discord_rpc': True,
        'language': 'en_us',
        'java_mode': 'default',
        'java_path': '',
        'skip_version_check': False,
    }


def get_minecraft_directory():
    settings = load_settings()
    if 'minecraft_directory' in settings:
        return Path(settings['minecraft_directory'])

    if sys.platform.startswith('win32'):
        return Path(os.getenv('APPDATA')) / '.minecraft'
    elif sys.platform.startswith('linux'):
        return Path.home() / '.minecraft'
    elif sys.platform.startswith('darwin'):
        return Path.home() / 'Library' / 'Application Support' / 'minecraft'
    return Path.home() / 'minecraft'


def resource_path(relative_path, base_dir=None):
    if base_dir is None:
        base_dir = Path(__file__).resolve().parents[1]
    return str(base_dir / relative_path)
