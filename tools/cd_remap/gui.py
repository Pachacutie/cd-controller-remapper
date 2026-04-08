"""Dear PyGui main window — layout, state management, callbacks."""
import dearpygui.dearpygui as dpg
from pathlib import Path

from . import VERSION
from .remap import (
    VALID_BUTTONS,
    ANALOG_BUTTONS,
    _apply_patched_xml,
    apply_swaps_contextual,
    extract_xml,
    remove_remap,
    show_bindings,
)
from .contexts import validate_swaps_contextual, VALID_CONTEXTS
from .presets import (
    BUILTIN_PRESETS,
    save_profile,
    load_profile,
    list_profiles,
    delete_profile,
    DEFAULT_PROFILES_DIR,
)
from .controller_draw import (
    BUTTON_POSITIONS,
    CLICKABLE_BUTTONS,
    draw_controller_body,
    draw_all_buttons,
    hit_test,
    update_button_color,
    get_pair_color,
    COLOR_DEFAULT,
    COLOR_SELECTED,
)

BUTTON_DISPLAY = {
    "buttonA": "A", "buttonB": "B", "buttonX": "X", "buttonY": "Y",
    "buttonLB": "LB", "buttonRB": "RB", "buttonLT": "LT", "buttonRT": "RT",
    "buttonLS": "LS", "buttonRS": "RS", "leftstick": "L-Stick", "rightstick": "R-Stick",
    "padU": "D-Up", "padD": "D-Down", "padL": "D-Left", "padR": "D-Right",
    "select": "Select", "start": "Start",
}


class RemapGUI:
    def __init__(self, game_dir: Path):
        self.game_dir = game_dir
        self.swaps: list[dict] = []
        self.selected_button: str | None = None
        self.active_profile: str | None = None
        self.pair_index = 0
        self.button_pair_map: dict[str, int] = {}
        self.drawlist = None
        self.binding_counts: dict[str, int] = {}
        self._load_binding_counts()

    def _load_binding_counts(self):
        try:
            bindings = show_bindings(self.game_dir)
            for b in bindings:
                for btn in VALID_BUTTONS:
                    if btn in b["key"].split():
                        self.binding_counts[btn] = self.binding_counts.get(btn, 0) + 1
        except Exception:
            pass

    def _get_context(self) -> str:
        val = dpg.get_value("context_radio")
        mapping = {"All": "all", "Gameplay": "gameplay", "Menus": "menus"}
        return mapping.get(val, "all")

    def _swapped_buttons(self) -> set[str]:
        return {s["source"] for s in self.swaps}

    def _add_swap_pair(self, src: str, tgt: str, ctx: str | None = None):
        if ctx is None:
            ctx = self._get_context()
        self.swaps.append({"source": src, "target": tgt, "context": ctx})
        self.swaps.append({"source": tgt, "target": src, "context": ctx})

        color_idx = self.pair_index
        self.button_pair_map[src] = color_idx
        self.button_pair_map[tgt] = color_idx
        self.pair_index += 1

        self._refresh_controller_colors()
        self._refresh_swap_list()
        self._set_status(f"Added: {BUTTON_DISPLAY[src]} <-> {BUTTON_DISPLAY[tgt]} ({ctx})")

    def _remove_swap_pair(self, btn: str):
        partner = None
        ctx = None
        for s in self.swaps:
            if s["source"] == btn:
                partner = s["target"]
                ctx = s["context"]
                break
        if partner is None:
            return

        self.swaps = [s for s in self.swaps
                      if not (s["context"] == ctx and s["source"] in (btn, partner))]
        self.button_pair_map.pop(btn, None)
        self.button_pair_map.pop(partner, None)

        self._refresh_controller_colors()
        self._refresh_swap_list()
        self._set_status(f"Removed: {BUTTON_DISPLAY[btn]} <-> {BUTTON_DISPLAY[partner]}")

    def _clear_all_swaps(self):
        self.swaps.clear()
        self.button_pair_map.clear()
        self.pair_index = 0
        self.selected_button = None
        self._refresh_controller_colors()
        self._refresh_swap_list()

    def _on_controller_click(self, sender, app_data):
        # Only handle clicks when mouse is within the drawlist bounds
        if not dpg.is_item_hovered("controller_drawlist"):
            return
        mouse_pos = dpg.get_drawing_mouse_pos()
        btn = hit_test(mouse_pos[0], mouse_pos[1])
        if btn is None:
            if self.selected_button:
                self.selected_button = None
                self._refresh_controller_colors()
            return

        swapped = self._swapped_buttons()

        if btn in swapped:
            self._remove_swap_pair(btn)
            self.selected_button = None
            return

        if self.selected_button is None:
            if btn in CLICKABLE_BUTTONS:
                self.selected_button = btn
                update_button_color(self.drawlist, btn, COLOR_SELECTED)
                self._set_status(f"Swap {BUTTON_DISPLAY[btn]} with...")
        else:
            if btn == self.selected_button:
                self.selected_button = None
                self._refresh_controller_colors()
                self._set_status("Cancelled.")
            elif btn in swapped:
                self._set_status(f"{BUTTON_DISPLAY[btn]} is already swapped. Remove it first.")
            else:
                src = self.selected_button
                self.selected_button = None

                if src in ANALOG_BUTTONS or btn in ANALOG_BUTTONS:
                    self._set_status(
                        f"Warning: swapping analog sticks also swaps axis scaling. "
                        f"Added {BUTTON_DISPLAY[src]} <-> {BUTTON_DISPLAY[btn]}"
                    )

                self._add_swap_pair(src, btn)

    def _refresh_controller_colors(self):
        for btn_id in CLICKABLE_BUTTONS:
            if btn_id in self.button_pair_map:
                color = get_pair_color(self.button_pair_map[btn_id])
            elif btn_id == self.selected_button:
                color = COLOR_SELECTED
            else:
                color = COLOR_DEFAULT
            update_button_color(self.drawlist, btn_id, color)

    def _refresh_swap_list(self):
        if dpg.does_item_exist("swap_list_group"):
            dpg.delete_item("swap_list_group", children_only=True)

        seen_pairs = set()
        for swap in self.swaps:
            pair_key = tuple(sorted([swap["source"], swap["target"]])) + (swap["context"],)
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            src_disp = BUTTON_DISPLAY[swap["source"]]
            tgt_disp = BUTTON_DISPLAY[swap["target"]]
            ctx = swap["context"].capitalize()
            color_idx = self.button_pair_map.get(swap["source"], 0)
            color = get_pair_color(color_idx)

            with dpg.group(horizontal=True, parent="swap_list_group"):
                dpg.add_text(f"{src_disp} <-> {tgt_disp}  ({ctx})", color=color[:3])
                dpg.add_button(
                    label="x",
                    callback=lambda s, a, u=swap["source"]: self._remove_swap_pair(u),
                    width=20, height=20,
                )

    def _refresh_sidebar(self):
        if dpg.does_item_exist("sidebar_group"):
            dpg.delete_item("sidebar_group", children_only=True)

        dpg.add_text("PRESETS", color=(200, 200, 200), parent="sidebar_group")
        dpg.add_separator(parent="sidebar_group")
        for name in BUILTIN_PRESETS:
            dpg.add_button(
                label=name, width=-1,
                callback=lambda s, a, u=name: self._load_preset(u),
                parent="sidebar_group",
            )

        dpg.add_spacer(height=10, parent="sidebar_group")
        dpg.add_text("PROFILES", color=(200, 200, 200), parent="sidebar_group")
        dpg.add_separator(parent="sidebar_group")
        for slug in list_profiles():
            dpg.add_button(
                label=slug, width=-1,
                callback=lambda s, a, u=slug: self._load_profile_by_slug(u),
                parent="sidebar_group",
            )

    def _load_preset(self, name: str):
        self._clear_all_swaps()
        self.active_profile = None
        swaps = BUILTIN_PRESETS[name]
        seen = set()
        for swap in swaps:
            pair = tuple(sorted([swap["source"], swap["target"]]))
            if pair in seen:
                continue
            seen.add(pair)
            self._add_swap_pair(swap["source"], swap["target"], swap["context"])
        self._set_status(f"Loaded preset: {name}")

    def _load_profile_by_slug(self, slug: str):
        try:
            data = load_profile(slug)
            self._clear_all_swaps()
            self.active_profile = slug
            seen = set()
            for swap in data["swaps"]:
                pair = tuple(sorted([swap["source"], swap["target"]]))
                if pair in seen:
                    continue
                seen.add(pair)
                self._add_swap_pair(swap["source"], swap["target"], swap["context"])
            self._set_status(f"Loaded profile: {data.get('name', slug)}")
        except Exception as e:
            self._set_status(f"Error loading profile: {e}")

    def _on_save(self):
        if not self.active_profile:
            self._set_status("No profile loaded. Use 'Save As' to create one.")
            return
        try:
            data = load_profile(self.active_profile)
            save_profile(data["name"], self.swaps)
            self._set_status(f"Saved: {data['name']}")
        except Exception as e:
            self._set_status(f"Error saving: {e}")

    def _on_save_as(self):
        dpg.configure_item("save_as_modal", show=True)

    def _on_save_as_confirm(self):
        name = dpg.get_value("save_as_name_input")
        if not name.strip():
            return
        dpg.configure_item("save_as_modal", show=False)
        try:
            path = save_profile(name.strip(), self.swaps)
            self.active_profile = path.stem
            self._refresh_sidebar()
            self._set_status(f"Saved as: {name.strip()}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_delete(self):
        if not self.active_profile:
            self._set_status("No profile selected to delete.")
            return
        dpg.configure_item("delete_confirm_modal", show=True)

    def _on_delete_confirm(self):
        dpg.configure_item("delete_confirm_modal", show=False)
        try:
            delete_profile(self.active_profile)
            self._clear_all_swaps()
            self.active_profile = None
            self._refresh_sidebar()
            self._set_status("Profile deleted.")
        except Exception as e:
            self._set_status(f"Error deleting: {e}")

    def _on_dry_run(self):
        errors = validate_swaps_contextual(self.swaps)
        if errors:
            self._set_status(f"Validation error: {errors[0]}")
            return
        try:
            xml = extract_xml(self.game_dir)
            patched = apply_swaps_contextual(xml, self.swaps)
            affected = sum(1 for a, b in zip(xml.split(b"\n"), patched.split(b"\n")) if a != b)
            self._set_status(f"Dry run: {affected} bindings would change.")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_apply(self):
        errors = validate_swaps_contextual(self.swaps)
        if errors:
            self._set_status(f"Validation error: {errors[0]}")
            return
        dpg.configure_item("apply_confirm_modal", show=True)

    def _on_apply_confirm(self):
        dpg.configure_item("apply_confirm_modal", show=False)
        try:
            xml = extract_xml(self.game_dir)
            patched = apply_swaps_contextual(xml, self.swaps)
            result = _apply_patched_xml(patched, self.game_dir)
            if result["ok"]:
                self._set_status(f"Applied! {result['affected']} bindings remapped.")
            else:
                self._set_status(f"Error: {result.get('errors', ['Unknown'])[0]}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_undo(self):
        dpg.configure_item("undo_confirm_modal", show=True)

    def _on_undo_confirm(self):
        dpg.configure_item("undo_confirm_modal", show=False)
        try:
            result = remove_remap(self.game_dir)
            if result["ok"]:
                self._set_status(f"Undo: {result['message']}")
            else:
                self._set_status(f"Error: {result.get('message', 'Unknown')}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _set_status(self, msg: str):
        if dpg.does_item_exist("status_text"):
            dpg.set_value("status_text", msg)

    def build(self):
        dpg.create_context()

        with dpg.theme() as global_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (30, 30, 35))
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (35, 35, 40))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (50, 50, 55))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
                dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 6)

        # Save As modal
        with dpg.window(label="Save As", modal=True, show=False,
                        tag="save_as_modal", width=300, height=100, no_resize=True):
            dpg.add_input_text(tag="save_as_name_input", hint="Profile name...", width=-1)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", callback=self._on_save_as_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("save_as_modal", show=False))

        # Delete confirm modal
        with dpg.window(label="Confirm Delete", modal=True, show=False,
                        tag="delete_confirm_modal", width=300, height=80, no_resize=True):
            dpg.add_text("Delete this profile permanently?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Delete", callback=self._on_delete_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("delete_confirm_modal", show=False))

        # Apply confirm modal
        with dpg.window(label="Confirm Apply", modal=True, show=False,
                        tag="apply_confirm_modal", width=350, height=80, no_resize=True):
            dpg.add_text("Apply remap to game files? (Backup is automatic)")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Apply", callback=self._on_apply_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("apply_confirm_modal", show=False))

        # Undo confirm modal
        with dpg.window(label="Confirm Undo", modal=True, show=False,
                        tag="undo_confirm_modal", width=350, height=80, no_resize=True):
            dpg.add_text("Remove all remaps and restore vanilla bindings?")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Undo All", callback=self._on_undo_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("undo_confirm_modal", show=False))

        # Main window
        with dpg.window(tag="main_window"):
            dpg.add_text(f"CD Controller Remapper v{VERSION}")
            dpg.add_separator()

            with dpg.group(horizontal=True):
                # Left sidebar
                with dpg.child_window(width=140, height=-60, tag="sidebar_window"):
                    with dpg.group(tag="sidebar_group"):
                        pass

                # Center area
                with dpg.group():
                    self.drawlist = dpg.add_drawlist(width=450, height=300, tag="controller_drawlist")
                    draw_controller_body(self.drawlist)
                    draw_all_buttons(self.drawlist)

                    with dpg.handler_registry():
                        dpg.add_mouse_click_handler(callback=self._on_controller_click)

                    dpg.add_separator()
                    dpg.add_text("Active Swaps:")
                    with dpg.group(tag="swap_list_group"):
                        pass

                # Right — context radio
                with dpg.child_window(width=100, height=120):
                    dpg.add_text("Context", color=(200, 200, 200))
                    dpg.add_radio_button(
                        items=["All", "Gameplay", "Menus"],
                        tag="context_radio", default_value="All",
                    )

            # Bottom action bar
            dpg.add_separator()
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", callback=self._on_save)
                dpg.add_button(label="Save As...", callback=self._on_save_as)
                dpg.add_button(label="Delete", callback=self._on_delete)
                dpg.add_spacer(width=40)
                dpg.add_button(label="Dry Run", callback=self._on_dry_run)
                dpg.add_button(label="Apply", callback=self._on_apply)
                dpg.add_button(label="Undo All", callback=self._on_undo)

            dpg.add_text(
                f"Ready - {self.game_dir}",
                tag="status_text", color=(150, 150, 150),
            )

        dpg.bind_theme(global_theme)
        self._refresh_sidebar()

        dpg.create_viewport(title=f"CD Controller Remapper v{VERSION}", width=800, height=550)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        dpg.start_dearpygui()
        dpg.destroy_context()


def run_gui(game_dir: Path):
    gui = RemapGUI(game_dir)
    gui.build()
