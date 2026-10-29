"""Exclusive, versioned AgentState snapshots for incident analysis/replay."""
from pathlib import Path

from .models import AgentState


def checkpoint(state: AgentState, root: str | Path) -> Path:
    dest = Path(root)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"state_{state.step_index:03d}_{state.status.value}.json"
    # Exclusive creation; a checkpoint is never silently overwritten.
    with path.open("x", encoding="utf-8") as stream:
        stream.write(state.model_dump_json(indent=2))
        stream.flush()
    return path


def load_checkpoint(path: str | Path) -> AgentState:
    return AgentState.model_validate_json(Path(path).read_text(encoding="utf-8"))
