"""Context system — maps user-facing contexts to engine InputGroup layers."""
from .remap import VALID_BUTTONS

VALID_CONTEXTS = frozenset(["all", "gameplay", "menus"])

CONTEXT_LAYERS = {
    "gameplay": {
        "UIHud_1", "UIHud_2", "UIHud_3", "UIHud_4",
        "UIHud_HighPriority", "Action", "QuickSlot",
        "QTE", "MiniGameWithAction", "GimmickInput",
    },
    "menus": {
        "UIMainMenu", "UIPopUp1", "UIPopUp2",
        "UIInfo", "UISystemPopup",
    },
}


def layer_matches_context(layer_name: str, context: str) -> bool:
    """Check if an InputGroup layer belongs to the given context."""
    if context == "all":
        return True
    if context not in CONTEXT_LAYERS:
        raise ValueError(f"Unknown context: {context}")
    return layer_name in CONTEXT_LAYERS[context]


def validate_swaps_contextual(swaps: list[dict]) -> list[str]:
    """Validate a v2 swap list. Returns list of error strings."""
    errors = []

    for swap in swaps:
        src, tgt, ctx = swap["source"], swap["target"], swap["context"]
        if src not in VALID_BUTTONS:
            errors.append(f"Unknown source button: {src}")
        if tgt not in VALID_BUTTONS:
            errors.append(f"Unknown target button: {tgt}")
        if src == tgt:
            errors.append(f"Self-swap not allowed: {src} -> {tgt}")
        if ctx not in VALID_CONTEXTS:
            errors.append(f"Unknown context: {ctx}")

    # Group swaps by context for per-context validation
    by_context: dict[str, list[dict]] = {}
    for swap in swaps:
        by_context.setdefault(swap["context"], []).append(swap)

    # Check for "all" conflicting with specific contexts
    all_sources = {s["source"] for s in by_context.get("all", [])}
    for ctx_name in ("gameplay", "menus"):
        for swap in by_context.get(ctx_name, []):
            if swap["source"] in all_sources:
                errors.append(
                    f"Conflict: {swap['source']} is swapped in 'all' and '{ctx_name}'. "
                    f"Remove the 'all' swap or the '{ctx_name}' swap."
                )

    # Per-context: check duplicate targets and missing reverse mappings
    for ctx_name, ctx_swaps in by_context.items():
        targets = [s["target"] for s in ctx_swaps]
        seen = set()
        for t in targets:
            if t in seen:
                errors.append(f"Duplicate target in '{ctx_name}': {t}")
            seen.add(t)

        sources = {s["source"] for s in ctx_swaps}
        for swap in ctx_swaps:
            if swap["target"] not in sources:
                errors.append(
                    f"Missing reverse in '{ctx_name}': {swap['target']} is a target "
                    f"but not remapped away. Add reverse mapping."
                )

    return errors
