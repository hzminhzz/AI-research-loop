"""Read-only PIT tool namespace. Delay exports to avoid harness/tool cycles."""
__all__ = ["PITGateway", "PITViolation"]


def __getattr__(name):
    if name in __all__:
        from .pit import PITGateway, PITViolation
        return {"PITGateway": PITGateway, "PITViolation": PITViolation}[name]
    raise AttributeError(name)
