"""XInput gamepad polling with edge detection for button presses."""

XINPUT_TO_BUTTON = {
    "A": "buttonA", "B": "buttonB", "X": "buttonX", "Y": "buttonY",
    "LEFT_SHOULDER": "buttonLB", "RIGHT_SHOULDER": "buttonRB",
    "LEFT_THUMB": "buttonLS", "RIGHT_THUMB": "buttonRS",
    "DPAD_UP": "padU", "DPAD_DOWN": "padD",
    "DPAD_LEFT": "padL", "DPAD_RIGHT": "padR",
    "START": "start", "BACK": "select",
}

TRIGGER_THRESHOLD = 0.5


class GamepadPoller:
    def __init__(self):
        try:
            import XInput
            self._xi = XInput
            self.available = True
        except ImportError:
            self._xi = None
            self.available = False
        self._prev_buttons: set[str] = set()
        self._prev_lt = False
        self._prev_rt = False
        self.connected = False

    def poll(self) -> str | None:
        """Poll for a new button press. Returns our button ID or None."""
        if not self.available:
            return None

        connected = self._xi.get_connected()
        if not any(connected):
            self.connected = False
            self._prev_buttons.clear()
            self._prev_lt = False
            self._prev_rt = False
            return None

        self.connected = True
        idx = connected.index(True)

        try:
            state = self._xi.get_state(idx)
        except Exception:
            return None

        # Digital buttons
        buttons = self._xi.get_button_values(state)
        current = {name for name, pressed in buttons.items() if pressed}
        new_presses = current - self._prev_buttons
        self._prev_buttons = current

        for xinput_name in new_presses:
            if xinput_name in XINPUT_TO_BUTTON:
                return XINPUT_TO_BUTTON[xinput_name]

        # Analog triggers with threshold
        lt, rt = self._xi.get_trigger_values(state)
        lt_pressed = lt > TRIGGER_THRESHOLD
        rt_pressed = rt > TRIGGER_THRESHOLD

        if lt_pressed and not self._prev_lt:
            self._prev_lt = lt_pressed
            self._prev_rt = rt_pressed
            return "buttonLT"
        if rt_pressed and not self._prev_rt:
            self._prev_lt = lt_pressed
            self._prev_rt = rt_pressed
            return "buttonRT"

        self._prev_lt = lt_pressed
        self._prev_rt = rt_pressed
        return None
