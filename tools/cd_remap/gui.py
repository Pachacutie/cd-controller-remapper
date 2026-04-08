"""Dear PyGui main window — action-based controller remapping."""
import dearpygui.dearpygui as dpg
from pathlib import Path

from . import VERSION
from .gamepad import GamepadPoller
from .remap import (
    _apply_patched_xml,
    apply_swaps_contextual,
    extract_xml,
    remove_remap,
)
from .actions import (
    ALL_CONTEXTS,
    CONTEXT_TO_SWAP_CONTEXT,
    auto_swap,
    diff_to_swaps,
    get_action_list,
    get_button_action_labels,
    get_defaults,
)
from .presets import (
    BUILTIN_PRESETS_V3,
    save_profile_v3,
    load_profile_v3,
    list_profiles,
    delete_profile,
)
from .controller_draw import (
    CLICKABLE_BUTTONS,
    draw_controller_body,
    draw_all_buttons,
    draw_all_action_labels,
    hit_test,
    update_button_color,
    get_pair_color,
    COLOR_DEFAULT,
    COLOR_HOVER,
    COLOR_SELECTED,
)

BUTTON_DISPLAY = {
    "buttonA": "A", "buttonB": "B", "buttonX": "X", "buttonY": "Y",
    "buttonLB": "LB", "buttonRB": "RB", "buttonLT": "LT", "buttonRT": "RT",
    "buttonLS": "LS", "buttonRS": "RS", "leftstick": "L-Stick", "rightstick": "R-Stick",
    "padU": "D-Up", "padD": "D-Down", "padL": "D-Left", "padR": "D-Right",
    "select": "Select", "start": "Start",
}

COLOR_CHANGED = (0, 200, 200, 255)


class RemapGUI:
    def __init__(self, game_dir: Path):
        self.game_dir = game_dir
        self.gamepad = GamepadPoller()
        self.active_tab = "combat"
        self.selected_action: str | None = None
        self.active_profile: str | None = None
        self.hovered_button: str | None = None
        self.drawlist = None

        # Action assignments per context: {context: {action_name: button_id}}
        self.assignments: dict[str, dict[str, str]] = {}
        for ctx in ALL_CONTEXTS:
            self.assignments[ctx] = get_defaults(ctx)

    def _get_changed_buttons(self) -> set[str]:
        """Buttons that differ from default in the active tab."""
        defaults = get_defaults(self.active_tab)
        current = self.assignments[self.active_tab]
        return {current[a] for a in current if current[a] != defaults.get(a)}

    def _on_tab_change(self, sender, app_data):
        # DPG may pass integer ID or string tag — resolve via alias
        tag = dpg.get_item_alias(app_data) if isinstance(app_data, int) else app_data
        tab_map = {"tab_combat": "combat", "tab_menus": "menus", "tab_horse": "horse"}
        self.active_tab = tab_map.get(tag, "combat")
        self.selected_action = None
        self._refresh_action_list()
        self._refresh_controller()

    def _on_action_click(self, sender, app_data, user_data):
        action_name = user_data
        self.selected_action = action_name
        btn = self.assignments[self.active_tab][action_name]
        update_button_color(self.drawlist, btn, COLOR_SELECTED)
        self._set_status(f"Press a button for {action_name}...")

    def _on_controller_click(self, sender, app_data):
        mouse_pos = dpg.get_drawing_mouse_pos()
        if not (0 <= mouse_pos[0] <= 450 and 0 <= mouse_pos[1] <= 300):
            return
        btn = hit_test(mouse_pos[0], mouse_pos[1])
        self._handle_button_input(btn)

    def _on_gamepad_button(self, btn: str):
        if self.selected_action:
            self._handle_button_input(btn)

    def _handle_button_input(self, btn: str | None):
        if btn is None:
            if self.selected_action:
                self.selected_action = None
                self._refresh_controller()
                self._set_status("Cancelled.")
            return

        if not self.selected_action:
            # No action selected — find what action is on this button and select it
            current = self.assignments[self.active_tab]
            for action_name, assigned_btn in current.items():
                if assigned_btn == btn:
                    self.selected_action = action_name
                    update_button_color(self.drawlist, btn, COLOR_SELECTED)
                    self._set_status(f"Press a button for {action_name}...")
                    return
            return

        # Action is selected — assign it to this button
        action = self.selected_action
        old_btn = self.assignments[self.active_tab][action]

        if btn == old_btn:
            self.selected_action = None
            self._refresh_controller()
            self._set_status("Cancelled.")
            return

        self.assignments[self.active_tab] = auto_swap(
            self.assignments[self.active_tab], action, btn,
        )
        self.selected_action = None

        # Find what was displaced
        displaced = None
        for a, b in self.assignments[self.active_tab].items():
            if b == old_btn and a != action:
                displaced = a
                break

        if displaced:
            self._set_status(
                f"{action} -> [{BUTTON_DISPLAY.get(btn, btn)}], "
                f"{displaced} -> [{BUTTON_DISPLAY.get(old_btn, old_btn)}]"
            )
        else:
            self._set_status(f"{action} -> [{BUTTON_DISPLAY.get(btn, btn)}]")

        self._refresh_action_list()
        self._refresh_controller()

    def _on_key_press(self, sender, app_data):
        if app_data == dpg.mvKey_Escape and self.selected_action:
            self.selected_action = None
            self._refresh_controller()
            self._set_status("Cancelled.")

    def _on_mouse_move(self, sender, app_data):
        mouse_pos = dpg.get_drawing_mouse_pos()
        in_drawlist = 0 <= mouse_pos[0] <= 450 and 0 <= mouse_pos[1] <= 300
        if not in_drawlist:
            if self.hovered_button:
                self._unhover()
            return

        btn = hit_test(mouse_pos[0], mouse_pos[1])
        if btn == self.hovered_button:
            return

        if self.hovered_button:
            self._unhover()

        if btn and btn in CLICKABLE_BUTTONS:
            base = self._get_button_color(btn)
            hover_color = COLOR_HOVER if base == COLOR_DEFAULT else tuple(min(255, c + 60) for c in base[:3]) + (255,)
            update_button_color(self.drawlist, btn, hover_color)
            self.hovered_button = btn
            # Show full action name in status bar
            current = self.assignments[self.active_tab]
            for action_name, assigned_btn in current.items():
                if assigned_btn == btn:
                    self._set_status(f"{action_name} [{BUTTON_DISPLAY.get(btn, btn)}]")
                    break
        else:
            self.hovered_button = None

    def _unhover(self):
        if self.hovered_button:
            update_button_color(self.drawlist, self.hovered_button,
                                self._get_button_color(self.hovered_button))
            self.hovered_button = None

    def _get_button_color(self, btn_id: str) -> tuple:
        changed = self._get_changed_buttons()
        if btn_id in changed:
            return COLOR_CHANGED
        return COLOR_DEFAULT

    def _refresh_controller(self):
        self.hovered_button = None
        for btn_id in CLICKABLE_BUTTONS:
            update_button_color(self.drawlist, btn_id, self._get_button_color(btn_id))
        labels = get_button_action_labels(self.active_tab, self.assignments[self.active_tab])
        draw_all_action_labels(self.drawlist, labels)

    def _refresh_action_list(self):
        if not dpg.does_item_exist("action_list_group"):
            return
        dpg.delete_item("action_list_group", children_only=True)

        defaults = get_defaults(self.active_tab)
        current = self.assignments[self.active_tab]
        actions = get_action_list(self.active_tab)

        for action in actions:
            btn = current.get(action.name, action.default_btn)
            btn_label = BUTTON_DISPLAY.get(btn, btn)
            is_changed = btn != defaults.get(action.name)
            color = (0, 200, 200) if is_changed else (180, 180, 180)

            with dpg.group(horizontal=True, parent="action_list_group"):
                dpg.add_text(f"{action.name}", color=color)
                dpg.add_spacer(width=10)
                dpg.add_button(
                    label=f"[{btn_label}]",
                    callback=self._on_action_click,
                    user_data=action.name,
                    width=50,
                )

    def _refresh_presets(self):
        if not dpg.does_item_exist("presets_group"):
            return
        dpg.delete_item("presets_group", children_only=True)

        for name in BUILTIN_PRESETS_V3:
            dpg.add_button(
                label=name, width=-1,
                callback=lambda s, a, u: self._load_preset(u),
                user_data=name, parent="presets_group",
            )

        dpg.add_spacer(height=8, parent="presets_group")
        dpg.add_separator(parent="presets_group")
        dpg.add_text("Profiles", color=(200, 200, 200), parent="presets_group")

        for slug in list_profiles():
            dpg.add_button(
                label=slug, width=-1,
                callback=lambda s, a, u: self._load_profile(u),
                user_data=slug, parent="presets_group",
            )

    def _load_preset(self, name: str):
        preset = BUILTIN_PRESETS_V3[name]
        for ctx in ALL_CONTEXTS:
            defaults = get_defaults(ctx)
            self.assignments[ctx] = dict(defaults)
            for action_name, btn in preset.get(ctx, {}).items():
                if action_name in self.assignments[ctx]:
                    self.assignments[ctx] = auto_swap(self.assignments[ctx], action_name, btn)
        self.active_profile = None
        self.selected_action = None
        self._refresh_action_list()
        self._refresh_controller()
        self._set_status(f"Loaded preset: {name}")

    def _load_profile(self, slug: str):
        try:
            data = load_profile_v3(slug)
            for ctx in ALL_CONTEXTS:
                defaults = get_defaults(ctx)
                self.assignments[ctx] = dict(defaults)
                for action_name, btn in data.get(ctx, {}).items():
                    if action_name in self.assignments[ctx]:
                        self.assignments[ctx] = auto_swap(self.assignments[ctx], action_name, btn)
            self.active_profile = slug
            self.selected_action = None
            self._refresh_action_list()
            self._refresh_controller()
            self._set_status(f"Loaded profile: {data.get('name', slug)}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_reset(self):
        for ctx in ALL_CONTEXTS:
            self.assignments[ctx] = get_defaults(ctx)
        self.selected_action = None
        self._refresh_action_list()
        self._refresh_controller()
        self._set_status("Reset to defaults.")

    def _on_save(self):
        dpg.configure_item("save_as_modal", show=True)

    def _on_save_confirm(self):
        name = dpg.get_value("save_name_input")
        if not name.strip():
            return
        dpg.configure_item("save_as_modal", show=False)
        # Only save changed-from-default actions
        save_data = {}
        for ctx in ALL_CONTEXTS:
            defaults = get_defaults(ctx)
            save_data[ctx] = {a: b for a, b in self.assignments[ctx].items() if b != defaults.get(a)}
        try:
            path = save_profile_v3(name.strip(), save_data)
            self.active_profile = path.stem
            self._refresh_presets()
            self._set_status(f"Saved: {name.strip()}")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_apply(self):
        dpg.configure_item("apply_modal", show=True)

    def _on_apply_confirm(self):
        dpg.configure_item("apply_modal", show=False)
        try:
            # Collect swaps from all contexts
            all_swaps = []
            for ctx in ALL_CONTEXTS:
                defaults = get_defaults(ctx)
                swap_ctx = CONTEXT_TO_SWAP_CONTEXT[ctx]
                swaps = diff_to_swaps(defaults, self.assignments[ctx], swap_ctx)
                all_swaps.extend(swaps)

            # Deduplicate (combat and horse share gameplay context)
            seen = set()
            unique_swaps = []
            for s in all_swaps:
                key = (s["source"], s["target"], s["context"])
                if key not in seen:
                    seen.add(key)
                    unique_swaps.append(s)

            if not unique_swaps:
                self._set_status("No changes to apply.")
                return

            xml = extract_xml(self.game_dir)
            patched = apply_swaps_contextual(xml, unique_swaps)
            result = _apply_patched_xml(patched, self.game_dir)
            if result["ok"]:
                self._set_status(f"Applied! {result['affected']} bindings remapped.")
            else:
                self._set_status("Error applying remap.")
        except Exception as e:
            self._set_status(f"Error: {e}")

    def _on_undo(self):
        try:
            result = remove_remap(self.game_dir)
            self._set_status(f"Undo: {result.get('message', 'Done')}")
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

        # Save modal
        with dpg.window(label="Save Profile", modal=True, show=False,
                        tag="save_as_modal", width=300, height=100, no_resize=True):
            dpg.add_input_text(tag="save_name_input", hint="Profile name...", width=-1)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", callback=self._on_save_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("save_as_modal", show=False))

        # Apply modal
        with dpg.window(label="Confirm Apply", modal=True, show=False,
                        tag="apply_modal", width=350, height=80, no_resize=True):
            dpg.add_text("Apply remap to game files? (Backup is automatic)")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Apply", callback=self._on_apply_confirm)
                dpg.add_button(label="Cancel",
                               callback=lambda: dpg.configure_item("apply_modal", show=False))

        # Main window
        with dpg.window(tag="main_window"):
            dpg.add_text(f"CD Controller Remapper v{VERSION}")
            dpg.add_separator()

            # Tab bar
            with dpg.tab_bar(callback=self._on_tab_change):
                dpg.add_tab(label="Combat", tag="tab_combat")
                dpg.add_tab(label="Menus", tag="tab_menus")
                dpg.add_tab(label="Horse", tag="tab_horse")

            with dpg.group(horizontal=True):
                # Left: action list + presets
                with dpg.child_window(width=220, height=-60):
                    dpg.add_text("Actions", color=(200, 200, 200))
                    dpg.add_separator()
                    with dpg.group(tag="action_list_group"):
                        pass
                    dpg.add_spacer(height=10)
                    dpg.add_separator()
                    dpg.add_text("Presets", color=(200, 200, 200))
                    with dpg.group(tag="presets_group"):
                        pass

                # Right: controller diagram
                with dpg.child_window(width=-1, height=-60):
                    labels = get_button_action_labels(self.active_tab, None)
                    self.drawlist = dpg.add_drawlist(width=450, height=300, tag="controller_drawlist")
                    draw_controller_body(self.drawlist)
                    draw_all_buttons(self.drawlist, labels)

                    with dpg.handler_registry():
                        dpg.add_mouse_click_handler(callback=self._on_controller_click)
                        dpg.add_mouse_move_handler(callback=self._on_mouse_move)
                        dpg.add_key_press_handler(callback=self._on_key_press)

            # Bottom bar
            dpg.add_separator()
            with dpg.group(horizontal=True):
                status = "Connected" if self.gamepad.connected else "Not detected"
                color = (100, 255, 100) if self.gamepad.connected else (150, 150, 150)
                dpg.add_text("Controller:", color=(200, 200, 200))
                dpg.add_text(status, tag="gamepad_status", color=color)
                dpg.add_spacer(width=20)
                dpg.add_button(label="Reset", callback=self._on_reset)
                dpg.add_button(label="Save", callback=self._on_save)
                dpg.add_button(label="Apply", callback=self._on_apply)
                dpg.add_button(label="Undo All", callback=self._on_undo)

            dpg.add_text(
                f"Ready - {self.game_dir}",
                tag="status_text", color=(150, 150, 150),
            )

        dpg.bind_theme(global_theme)
        self._refresh_action_list()
        self._refresh_presets()

        dpg.create_viewport(title=f"CD Controller Remapper v{VERSION}", width=800, height=550)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)

        prev_connected = self.gamepad.connected
        while dpg.is_dearpygui_running():
            btn = self.gamepad.poll()
            if btn:
                self._on_gamepad_button(btn)

            if self.gamepad.connected != prev_connected:
                prev_connected = self.gamepad.connected
                if self.gamepad.connected:
                    dpg.set_value("gamepad_status", "Connected")
                    dpg.configure_item("gamepad_status", color=(100, 255, 100))
                else:
                    dpg.set_value("gamepad_status", "Not detected")
                    dpg.configure_item("gamepad_status", color=(150, 150, 150))

            dpg.render_dearpygui_frame()

        dpg.destroy_context()


def run_gui(game_dir: Path):
    gui = RemapGUI(game_dir)
    gui.build()
