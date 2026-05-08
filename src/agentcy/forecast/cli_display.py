"""Rich-based visual pipeline display for the CLI."""

from __future__ import annotations

import sys
import time
from typing import Optional

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.text import Text


STEPS = ["ontology", "graph", "profiles", "simulation", "report", "visuals"]

STEP_LABELS = {
    "ontology": "Ontology",
    "graph": "Graph",
    "profiles": "Profiles",
    "simulation": "Simulation",
    "report": "Report",
    "visuals": "Visuals",
}

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class StepState:
    __slots__ = ("status", "message", "elapsed", "_start")

    def __init__(self) -> None:
        self.status: str = "pending"  # pending | running | done | failed
        self.message: str = ""
        self.elapsed: Optional[float] = None
        self._start: Optional[float] = None

    def start(self) -> None:
        self.status = "running"
        self._start = time.monotonic()

    def complete(self, stats: str = "") -> None:
        self.status = "done"
        self.message = stats
        if self._start is not None:
            self.elapsed = time.monotonic() - self._start

    def fail(self, error: str = "") -> None:
        self.status = "failed"
        self.message = error
        if self._start is not None:
            self.elapsed = time.monotonic() - self._start

    def update(self, message: str) -> None:
        self.message = message


class PipelineDisplay:
    """Live-updating CLI pipeline view.

    In json_mode, falls back to plain stderr lines (no rich rendering).
    """

    def __init__(
        self,
        project_name: str = "",
        run_id: str = "",
        provider: str = "",
        platform: str = "",
        json_mode: bool = False,
    ) -> None:
        self.project_name = project_name
        self.run_id = run_id
        self.provider = provider
        self.platform = platform
        self.json_mode = json_mode

        self._steps = {name: StepState() for name in STEPS}
        self._tick = 0
        self._console = Console(stderr=True)
        self._live: Optional[Live] = None

    # -- public API --

    def start(self) -> None:
        if self.json_mode:
            return
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=8,
            transient=True,
        )
        self._live.start()

    def start_step(self, name: str) -> None:
        self._steps[name].start()
        if self.json_mode:
            print(f"[{self.run_id}] {STEP_LABELS.get(name, name).lower()}...", file=sys.stderr)
        else:
            self._refresh()

    def update_step(self, name: str, message: str) -> None:
        self._steps[name].update(message)
        if not self.json_mode:
            self._refresh()

    def complete_step(self, name: str, stats: str = "") -> None:
        self._steps[name].complete(stats)
        if self.json_mode:
            parts = [f"[{self.run_id}] {STEP_LABELS.get(name, name).lower()} done"]
            if stats:
                parts.append(stats)
            print(" — ".join(parts), file=sys.stderr)
        else:
            self._refresh()

    def fail_step(self, name: str, error: str = "") -> None:
        self._steps[name].fail(error)
        if self.json_mode:
            print(f"[{self.run_id}] {STEP_LABELS.get(name, name).lower()} FAILED: {error}", file=sys.stderr)
        else:
            self._refresh()

    def finish(self) -> None:
        if self._live is not None:
            # Final render (non-transient) so the result persists
            self._live.stop()
            self._console.print(self._render())

    # -- rendering --

    def _refresh(self) -> None:
        self._tick += 1
        if self._live is not None:
            self._live.update(self._render())

    def _render(self) -> Group:
        # header
        title = Text("  agentcy-echo run", style="bold cyan")
        if self.project_name:
            title.append(f" ─ {self.project_name}", style="dim")

        grid = Table.grid(padding=(0, 2))
        grid.add_column(width=2)   # icon
        grid.add_column(width=14)  # label
        grid.add_column(min_width=30)  # message
        grid.add_column(width=6, justify="right")  # time

        for name in STEPS:
            state = self._steps[name]
            icon = self._icon(state.status)
            label_style = "bold" if state.status == "running" else ("dim" if state.status == "pending" else "")
            label = Text(STEP_LABELS[name], style=label_style)

            msg = Text(state.message, style="dim" if state.status == "done" else "")
            if state.status == "failed":
                msg = Text(state.message, style="red")

            elapsed_str = ""
            if state.elapsed is not None:
                elapsed_str = self._fmt_elapsed(state.elapsed)
            elif state.status == "running" and state._start is not None:
                elapsed_str = self._fmt_elapsed(time.monotonic() - state._start)

            grid.add_row(icon, label, msg, Text(elapsed_str, style="dim"))

        # footer
        footer_parts = [p for p in [self.run_id, self.provider, self.platform] if p]
        footer = Text("  " + " · ".join(footer_parts), style="dim")

        return Group(Text(""), title, Text(""), grid, Text(""), footer)

    def _icon(self, status: str) -> Text:
        if status == "done":
            return Text("✓", style="green")
        if status == "failed":
            return Text("✗", style="red bold")
        if status == "running":
            frame = _SPINNER_FRAMES[self._tick % len(_SPINNER_FRAMES)]
            return Text(frame, style="cyan")
        return Text("○", style="dim")

    @staticmethod
    def _fmt_elapsed(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes}m{secs:02d}s"
