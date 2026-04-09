"""Core remap logic -- extract, swap, apply via in-place PAZ patching."""
import json
import re
from pathlib import Path

from .vendor.paz_parse import parse_pamt
from .vendor.paz_crypto import decrypt, lz4_decompress
from .vendor.paz_patcher import apply_paz_patch, remove_paz_patch

TARGET_FILE = "ui/inputmap_common.xml"
PAZ_FOLDER = "0012"

VALID_BUTTONS = frozenset([
    "buttonA", "buttonB", "buttonX", "buttonY",
    "buttonLB", "buttonRB", "buttonLT", "buttonRT",
    "buttonLS", "buttonRS", "leftstick", "rightstick",
    "padU", "padD", "padL", "padR", "select", "start",
])

ANALOG_BUTTONS = frozenset(["leftstick", "rightstick"])

# Matches the Key="..." value inside GamePad elements
_KEY_ATTR_RE = re.compile(rb'(<GamePad\b[^>]*\bKey=")([^"]+)(")')

def _detect_game_dir() -> Path:
    """Auto-detect Crimson Desert install via common Steam library paths."""
    candidates = [
        Path("C:/Program Files (x86)/Steam/steamapps/common/Crimson Desert"),
        Path("C:/Program Files/Steam/steamapps/common/Crimson Desert"),
    ]
    # Check additional Steam library folders from libraryfolders.vdf
    vdf = Path("C:/Program Files (x86)/Steam/steamapps/libraryfolders.vdf")
    if vdf.exists():
        import re as _re
        for match in _re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(errors="ignore")):
            candidates.append(Path(match.group(1)) / "steamapps/common/Crimson Desert")
    for p in candidates:
        if (p / PAZ_FOLDER / "0.pamt").exists():
            return p
    return Path(".")  # Fallback — user must pass --game-dir


DEFAULT_GAME_DIR = _detect_game_dir()


def validate_swaps(swaps: dict[str, str]) -> list[str]:
    """Return list of error strings. Empty list = valid."""
    errors = []
    for src, tgt in swaps.items():
        if src not in VALID_BUTTONS:
            errors.append(f"Unknown source button: {src}")
        if tgt not in VALID_BUTTONS:
            errors.append(f"Unknown target button: {tgt}")
        if src == tgt:
            errors.append(f"Self-swap not allowed: {src} -> {tgt}")

    targets = list(swaps.values())
    seen = set()
    for t in targets:
        if t in seen:
            errors.append(f"Duplicate target: {t} (two buttons mapped to same target)")
        seen.add(t)

    # Detect unidirectional swaps that would cause button collisions
    for tgt in swaps.values():
        if tgt not in swaps:
            errors.append(
                f"Collision: {tgt} is a swap target but not remapped away. "
                f"Add reverse mapping (e.g., \"{tgt}\": \"{next(s for s, t in swaps.items() if t == tgt)}\")"
            )

    return errors


def apply_swaps(xml_bytes: bytes, swaps: dict[str, str]) -> bytes:
    """Apply button swaps to all GamePad Key attributes. Simultaneous replacement."""
    placeholders = {src: f"\x00SWAP_{i}\x00" for i, src in enumerate(swaps)}

    def replace_key(match: re.Match) -> bytes:
        prefix = match.group(1)
        key_val = match.group(2).decode("utf-8")
        suffix = match.group(3)

        for src, ph in placeholders.items():
            key_val = re.sub(rf'\b{re.escape(src)}\b', ph, key_val)

        for src, ph in placeholders.items():
            key_val = key_val.replace(ph, swaps[src])

        return prefix + key_val.encode("utf-8") + suffix

    return _KEY_ATTR_RE.sub(replace_key, xml_bytes)


_INPUTGROUP_LAYER_RE = re.compile(rb'<InputGroup\b[^>]*\bLayerName="([^"]+)"')


def apply_swaps_contextual(xml_bytes: bytes, swaps: list[dict]) -> bytes:
    """Apply context-aware button swaps. Each swap has source, target, context."""
    from .contexts import layer_matches_context

    # Group swaps by context for efficient lookup
    by_context: dict[str, dict[str, str]] = {}
    for swap in swaps:
        ctx = swap["context"]
        by_context.setdefault(ctx, {})[swap["source"]] = swap["target"]

    current_layer = None
    result_lines = []

    for line in xml_bytes.split(b"\n"):
        # Track current InputGroup layer
        layer_match = _INPUTGROUP_LAYER_RE.search(line)
        if layer_match:
            current_layer = layer_match.group(1).decode("utf-8")

        # Find applicable swaps for current layer
        applicable_swaps = {}
        for ctx, swap_map in by_context.items():
            if current_layer is None:
                # Before any InputGroup — only "all" applies
                if ctx == "all":
                    applicable_swaps.update(swap_map)
            else:
                if layer_matches_context(current_layer, ctx):
                    applicable_swaps.update(swap_map)

        if applicable_swaps:
            # Apply swaps to this line using the existing placeholder technique
            def replace_key(match: re.Match) -> bytes:
                prefix = match.group(1)
                key_val = match.group(2).decode("utf-8")
                suffix = match.group(3)

                placeholders = {src: f"\x00SWAP_{i}\x00"
                                for i, src in enumerate(applicable_swaps)}

                for src, ph in placeholders.items():
                    key_val = re.sub(rf'\b{re.escape(src)}\b', ph, key_val)
                for src, ph in placeholders.items():
                    key_val = key_val.replace(ph, applicable_swaps[src])

                return prefix + key_val.encode("utf-8") + suffix

            line = _KEY_ATTR_RE.sub(replace_key, line)

        result_lines.append(line)

    return b"\n".join(result_lines)


def count_affected(xml_bytes: bytes, swaps: dict[str, str]) -> int:
    """Count how many GamePad entries would be changed by the swap config."""
    count = 0
    for match in _KEY_ATTR_RE.finditer(xml_bytes):
        key_val = match.group(2).decode("utf-8")
        for src in swaps:
            if re.search(rf'\b{re.escape(src)}\b', key_val):
                count += 1
                break
    return count


def extract_xml(game_dir: Path = DEFAULT_GAME_DIR) -> bytes:
    """Extract and decrypt ui/inputmap_common.xml from PAZ 0012."""
    paz_dir = game_dir / PAZ_FOLDER
    if not paz_dir.exists():
        raise FileNotFoundError(
            f"Game directory not found: {game_dir}\n"
            f"Make sure Crimson Desert is installed, or use --game-dir to specify the path."
        )
    entries = parse_pamt(str(paz_dir / "0.pamt"), str(paz_dir))
    entry = next((e for e in entries if e.path == TARGET_FILE), None)
    if entry is None:
        raise FileNotFoundError(f"{TARGET_FILE} not found in PAZ folder {PAZ_FOLDER}")

    with open(entry.paz_file, "rb") as f:
        f.seek(entry.offset)
        raw = f.read(entry.comp_size)

    if entry.encrypted:
        raw = decrypt(raw, entry.path)
    if entry.compressed:
        raw = lz4_decompress(raw, entry.orig_size)

    return raw


def apply_remap(
    swaps: dict[str, str],
    game_dir: Path = DEFAULT_GAME_DIR,
    dry_run: bool = False,
) -> dict:
    """Extract XML, apply swaps, patch PAZ in-place. Returns summary dict."""
    errors = validate_swaps(swaps)
    if errors:
        return {"ok": False, "errors": errors}

    xml = extract_xml(game_dir)
    affected = count_affected(xml, swaps)
    patched = apply_swaps(xml, swaps)

    if dry_run:
        return {"ok": True, "affected": affected, "dry_run": True}

    result = apply_paz_patch(patched, game_dir)
    result["affected"] = affected
    return result


def _apply_patched_xml(
    patched_xml: bytes,
    game_dir: Path = DEFAULT_GAME_DIR,
) -> dict:
    """Patch PAZ with pre-patched XML bytes. Used by GUI for context-aware apply."""
    original_xml = extract_xml(game_dir)
    affected = sum(1 for a, b in zip(original_xml.split(b"\n"), patched_xml.split(b"\n")) if a != b)

    result = apply_paz_patch(patched_xml, game_dir)
    result["affected"] = affected
    return result


def remove_remap(game_dir: Path = DEFAULT_GAME_DIR) -> dict:
    """Restore vanilla PAZ/PAMT/PAPGT from backup."""
    return remove_paz_patch(game_dir)


def show_bindings(game_dir: Path = DEFAULT_GAME_DIR) -> list[dict]:
    """Extract current vanilla bindings. Returns list of {action, button, method}."""
    xml = extract_xml(game_dir)
    bindings = []
    input_re = re.compile(rb'<Input\s+Name="([^"]+)"')
    gamepad_re = re.compile(rb'<GamePad\s+Key="([^"]+)"\s+Method="([^"]+)"')

    current_action = "unknown"
    for line in xml.split(b"\n"):
        m = input_re.search(line)
        if m:
            current_action = m.group(1).decode("utf-8")
        m = gamepad_re.search(line)
        if m:
            bindings.append({
                "action": current_action,
                "key": m.group(1).decode("utf-8"),
                "method": m.group(2).decode("utf-8"),
            })
    return bindings


def load_config(path: str) -> dict[str, str]:
    """Load remap config JSON. Returns the swaps dict."""
    with open(path) as f:
        data = json.load(f)
    return data.get("swaps", {})
