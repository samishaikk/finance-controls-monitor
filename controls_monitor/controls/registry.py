from controls_monitor.controls.base import Control
REGISTRY: dict[str, type[Control]] = {}



class UnknownControlError(Exception):
    pass


def register(cls):
    """Class decorator: makes a control available to the runner."""
    if not cls.control_id:
        raise ValueError(f"{cls.__name__} has no control_id")
    if cls.control_id in REGISTRY:
        raise ValueError(f"control {cls.control_id} is already registered")
    REGISTRY[cls.control_id] = cls
    return cls


def build_controls(config, registry=None):
    """Create a Control for every enabled entry in the config."""
    registry = REGISTRY if registry is None else registry
    controls = []
    for control_id, settings in config.controls.by_id().items():
        if not settings.enabled:
            continue
        if control_id not in registry:
            raise UnknownControlError(
                f"{control_id} is enabled in the config but no control is registered for it"
            )
        controls.append(registry[control_id](settings))
    return controls