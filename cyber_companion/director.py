"""Single authority that translates system state into avatar behavior."""

from __future__ import annotations

from cyber_companion.behavior import BehaviorEngine
from cyber_companion.events import Event
from cyber_companion.presentation import PresentationCommand
from cyber_companion.state import StateStore


class BehaviorDirector:
    def __init__(self, state: StateStore, engine: BehaviorEngine, renderer: object) -> None:
        self.state = state
        self.engine = engine
        self.renderer = renderer
        self._current: PresentationCommand | None = None

    def initialize(self, publish: bool = False) -> None:
        self.state.initialize()
        command = self.engine.resolve(self.state.behavior_state())
        self.state.set_presentation(command)
        if publish:
            self._publish(command)

    def handle(self, event: Event) -> None:
        self.state.handle(event)
        command = self.engine.resolve(self.state.behavior_state())
        self.state.set_presentation(command)
        self._publish(command)

    def _publish(self, command: PresentationCommand) -> None:
        if command == self._current:
            return
        self.renderer.apply(command)
        self._current = command
