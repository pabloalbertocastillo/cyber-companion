"""Logical desktop geometry and ambient visibility, independent of GTK."""
from dataclasses import dataclass
import math

AVATAR_WIDTH = 384
AVATAR_HEIGHT = 336
MAX_MARGIN = 32768
AMBIENT_OPACITY = .65


def companion_monitor(names, active=None, preferred="", current=None):
    """Automatic placement stays off the focused output, stable on 3+ screens.

    A connected explicit choice wins. Missing focus or a disconnected preference
    keeps the current output when possible; one screen remains usable.
    """
    if preferred in names:
        return preferred
    available = [name for name in names if name != active] or list(names)
    return current if current in available else next(iter(available), None)


@dataclass(frozen=True)
class Output:
    name: str
    x: int
    y: int
    width: int
    height: int


def drag_placement(outputs, pointer, hotspot, size):
    """Follow the pointer's output, including negative/stacked logical layouts.

    Keep the full avatar reachable at output edges and across gaps. Coordinates
    are application pixels; multiplying by output scale would break HiDPI.
    """
    if not outputs:
        return None
    px, py = pointer
    def distance(output):
        dx = max(output.x-px, 0, px-(output.x+output.width-1))
        dy = max(output.y-py, 0, py-(output.y+output.height-1))
        return dx*dx+dy*dy
    output = min(outputs, key=distance)
    max_x = max(0, output.width-size[0])
    max_y = max(0, output.height-size[1])
    left = max(0, min(max_x, px-hotspot[0]-output.x))
    top = max(0, min(max_y, py-hotspot[1]-output.y))
    return output.name, min(MAX_MARGIN, round(max_x-left)), min(MAX_MARGIN, round(max_y-top))


class AmbientVisibility:
    """A short grace period, gentle fade out, and prompt hover recovery."""
    def __init__(self, now):
        self.last_active = now
        self.opacity = 1.

    def step(self, now, dt, active=False, reduced=False):
        if active:
            self.last_active = now
        target = 1. if active or now-self.last_active < 2.5 else AMBIENT_OPACITY
        if reduced:
            self.opacity = target
        else:
            duration = .075 if target > self.opacity else .65
            self.opacity += (target-self.opacity)*(1-math.exp(-max(0, dt)/duration))
            if abs(target-self.opacity) < .002:
                self.opacity = target
        return self.opacity
