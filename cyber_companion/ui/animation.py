"""Renderer-local atlas state machine; independent of GTK and system observations."""
import time


class Animation:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.target = "idle"
        self.current = "idle"
        self.row = 0
        self.since = clock()
        self.transition = False

    def select(self, presence: str):
        self.target = "media" if presence == "media" else "busy" if presence in ("warning", "busy") else "idle"

    def frame(self, reduced=False):
        now = self.clock()
        if self.transition and now - self.since >= 24 * .042:
            self.transition = False
            self.row = {"idle": 0, "media": 2, "busy": 5}[self.current]
            self.since = now
        if not self.transition and self.current != self.target:
            if self.current != "idle":
                self.row = 3 if self.current == "media" else 6
                self.current = "idle"
            else:
                self.current = self.target
                self.row = 1 if self.current == "media" else 4
            self.transition = True
            self.since = now
        if reduced:
            return {"idle": 0, "media": 2, "busy": 5}[self.target], 0
        # The apparition drifts rather than bouncing through a one-second idle loop.
        interval = {"idle": .11, "media": .065, "busy": .075}[self.current]
        return self.row, min(23, int((now-self.since)/.042)) if self.transition else int((now-self.since)/interval) % 24
