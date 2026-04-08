"""Built-in presets and profile management."""
import json
import os
import re
from pathlib import Path


BUILTIN_PRESETS: dict[str, list[dict]] = {
    "Soulslike": [
        {"source": "buttonA", "target": "buttonB", "context": "all"},
        {"source": "buttonB", "target": "buttonA", "context": "all"},
        {"source": "buttonX", "target": "buttonY", "context": "all"},
        {"source": "buttonY", "target": "buttonX", "context": "all"},
    ],
    "Southpaw": [
        {"source": "buttonLS", "target": "buttonRS", "context": "all"},
        {"source": "buttonRS", "target": "buttonLS", "context": "all"},
        {"source": "buttonLB", "target": "buttonRB", "context": "all"},
        {"source": "buttonRB", "target": "buttonLB", "context": "all"},
    ],
    "Trigger Swap": [
        {"source": "buttonLT", "target": "buttonRT", "context": "all"},
        {"source": "buttonRT", "target": "buttonLT", "context": "all"},
        {"source": "buttonLB", "target": "buttonRB", "context": "all"},
        {"source": "buttonRB", "target": "buttonLB", "context": "all"},
    ],
}

DEFAULT_PROFILES_DIR = Path(os.environ.get("APPDATA", ".")) / "cd_remap" / "profiles"


def _slugify(name: str) -> str:
    """Convert display name to filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def save_profile(
    name: str,
    swaps: list[dict],
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> Path:
    """Save a profile to JSON. Returns the file path."""
    profiles_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(name)
    data = {
        "format_version": "2.0",
        "name": name,
        "swaps": swaps,
    }
    path = profiles_dir / f"{slug}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def load_profile(
    slug: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> dict:
    """Load a profile by slug. Auto-migrates v1 format."""
    path = profiles_dir / f"{slug}.json"
    data = json.loads(path.read_text())

    # v1 migration: {"swaps": {"A": "B"}} -> v2 list format
    if isinstance(data.get("swaps"), dict):
        old_swaps = data["swaps"]
        data = {
            "format_version": "2.0",
            "name": data.get("name", slug),
            "swaps": [
                {"source": src, "target": tgt, "context": "all"}
                for src, tgt in old_swaps.items()
            ],
        }

    return data


def list_profiles(profiles_dir: Path = DEFAULT_PROFILES_DIR) -> list[str]:
    """List saved profile slugs."""
    if not profiles_dir.exists():
        return []
    return [p.stem for p in sorted(profiles_dir.glob("*.json"))]


def delete_profile(
    slug: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> None:
    """Delete a profile by slug."""
    path = profiles_dir / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {slug}")
    path.unlink()


BUILTIN_PRESETS_V3: dict[str, dict[str, dict[str, str]]] = {
    "Soulslike": {
        "combat": {
            "Sprint/Run": "buttonB",
            "Dodge/Roll": "buttonA",
            "Jump": "buttonY",
            "Kick/Unarmed": "buttonX",
        },
        "menus": {},
        "horse": {},
    },
    "Southpaw": {
        "combat": {
            "Crouch/Slide": "buttonRS",
            "Force Palm": "buttonLS",
            "Block/Parry": "buttonRB",
            "Basic Attack": "buttonLB",
        },
        "menus": {},
        "horse": {},
    },
    "Trigger Swap": {
        "combat": {
            "Aim Ranged": "buttonRT",
            "Power Attack": "buttonLT",
            "Block/Parry": "buttonRB",
            "Basic Attack": "buttonLB",
        },
        "menus": {},
        "horse": {},
    },
}


def save_profile_v3(
    name: str,
    assignments: dict[str, dict[str, str]],
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> Path:
    """Save a v3 action-assignment profile."""
    profiles_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(name)
    data = {
        "format_version": "3.0",
        "name": name,
        **assignments,
    }
    path = profiles_dir / f"{slug}.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def load_profile_v3(
    slug: str,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
) -> dict:
    """Load a v3 profile. Returns dict with name, format_version, combat, menus, horse."""
    path = profiles_dir / f"{slug}.json"
    data = json.loads(path.read_text())

    # v2 migration: convert swap list to action assignments
    if data.get("format_version") == "2.0" and "swaps" in data:
        from .actions import get_defaults
        combat_defaults = get_defaults("combat")
        assignments = dict(combat_defaults)
        for swap in data["swaps"]:
            for action, btn in combat_defaults.items():
                if btn == swap["source"]:
                    assignments[action] = swap["target"]
        changed = {a: b for a, b in assignments.items() if b != combat_defaults[a]}
        data = {
            "format_version": "3.0",
            "name": data.get("name", slug),
            "combat": changed,
            "menus": {},
            "horse": {},
        }

    if "combat" not in data:
        data["combat"] = {}
    if "menus" not in data:
        data["menus"] = {}
    if "horse" not in data:
        data["horse"] = {}

    return data
