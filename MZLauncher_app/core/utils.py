import os
import sys
import json
import datetime
from pathlib import Path
import uuid

import minecraft_launcher_lib
from packaging.version import Version, InvalidVersion

from MZLauncher_app.settings.settings import get_minecraft_directory


def get_appdata_path():
    if sys.platform == "win32":
        base_dir = os.getenv("APPDATA")
        if base_dir:
            return Path(base_dir) / "MaZultLauncher"
    elif sys.platform.startswith("linux"):
        base_dir = os.getenv("XDG_CONFIG_HOME")
        if base_dir:
            return Path(base_dir) / "MaZultLauncher"
        return Path.home() / ".config" / "MaZultLauncher"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MaZultLauncher"

    return Path.home() / ".mazultlauncher"


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(base_path, relative_path)


def get_tmp_dir():
    tmp = get_appdata_path() / 'tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp

def list_available_languages():
    lang_dir = resource_path("lang")
    langs = {}
    if not os.path.exists(lang_dir):
        print("[Lang] No lang directory found.")
        return langs

    for file in os.listdir(lang_dir):
        if file.endswith(".json"):
            lang_code = file.replace(".json", "")
            try:
                with open(os.path.join(lang_dir, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                    lang_name = data.get("langinfo", lang_code)
                    langs[lang_code] = lang_name
            except Exception as e:
                print(f"[Lang] Failed to read {file}: {e}")
    return langs

def load_language(lang_code="en_us"):
    lang_path = os.path.join(resource_path("lang"), f"{lang_code}.json")
    if os.path.exists(lang_path):
        try:
            with open(lang_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Lang] Error loading {lang_code}: {e}")
    print(f"[Lang] Missing language file: {lang_code}, fallback to English.")
    if lang_code != "en_us":
        return load_language("en_us")
    return {}

def Launcher_profiles_json(mc_dir):
    profile_path = os.path.join(mc_dir, "launcher_profiles.json")

    default_data = {
        "profiles": {
            "Mazult": {
                "created": "2020-01-01T00:00:00.000Z",
                "icon": "Grass",
                "lastUsed": "2020-01-01T00:00:00.000Z",
                "lastVersionId": "latest-release",
                "name": "latest-release",
                "type": "release"
            }
        },
        "settings": {
            "crashAssistance": True,
            "enableAdvanced": False,
            "enableAnalytics": False,
            "enableHistorical": False,
            "enableReleases": True,
            "enableSnapshots": False,
            "keepLauncherOpen": False,
            "profileSorting": "",
            "showGameLog": False,
            "showMenu": False,
            "soundOn": True
        },
        "version": 3,
        "clientToken": str(uuid.uuid4())
    }

    if not os.path.exists(profile_path):
        try:
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=4)
        except Exception:
            pass

VERSION_FILE = get_appdata_path() / "versions.json"

def minecraft_version_key(version_string: str):
    try:
        return Version(version_string)
    except InvalidVersion:
        return Version("0.0.0-alpha")

def get_installed_versions():
    installed_versions = []
    versions_dir = get_minecraft_directory() / "versions"
    if os.path.exists(versions_dir):
        for folder_name in os.listdir(versions_dir):
            if os.path.isdir(os.path.join(versions_dir, folder_name)) and \
               os.path.exists(os.path.join(versions_dir, folder_name, f"{folder_name}.json")):
                installed_versions.append(folder_name)

    return sorted(installed_versions, key=minecraft_version_key, reverse=True)

def get_available_versions(filters, offline=False):
    versions = []
    latest_release_id = None
    try:
        if offline:
            raise Exception("Forced offline")
        mc_versions = minecraft_launcher_lib.utils.get_version_list()
        serializable_versions = []

        for v in mc_versions:
            if v.get('type') == 'release' and latest_release_id is None:
                latest_release_id = v['id']
            if isinstance(v.get('releaseTime'), datetime.datetime):
                v['releaseTime'] = v['releaseTime'].isoformat()
            serializable_versions.append(v)

        with open(VERSION_FILE, "w") as f:
            json.dump(serializable_versions, f)

    except Exception as e:
        print("Offline or error fetching versions:", e)
        if os.path.exists(VERSION_FILE):
            try:
                with open(VERSION_FILE, "r") as f:
                    mc_versions = json.load(f)

                for v in mc_versions:
                    if v.get('type') == 'release' and latest_release_id is None:
                        latest_release_id = v['id']
            except Exception:
                return [("Offline: No cached versions", "")], None
        else:
            return [("Offline: No cached versions", "")], None

    filtered_versions = []
    version_types = {
        "release": filters.get("release", True),
        "snapshot": filters.get("snapshot", False),
        "old_beta": filters.get("beta", False),
        "old_alpha": filters.get("alpha", False),
    }

    for v in mc_versions:
        if version_types.get(v.get('type', 'release'), False):
            label = f"{v.get('type', 'release').capitalize()} - {v['id']}"
            filtered_versions.append((label, v['id']))

    return filtered_versions, latest_release_id