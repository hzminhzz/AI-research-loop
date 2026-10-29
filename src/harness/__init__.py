"""Research harness namespace; no eager import cycles."""
__all__ = ["ReActEngine", "EnginePolicy"]


def __getattr__(name):
    if name in __all__:
        from .engine import ReActEngine, EnginePolicy
        return {"ReActEngine": ReActEngine, "EnginePolicy": EnginePolicy}[name]
    raise AttributeError(name)
