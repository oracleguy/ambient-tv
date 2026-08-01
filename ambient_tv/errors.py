class AmbientTvError(Exception):
    """Base class for expected user-facing errors."""


class ConfigError(AmbientTvError):
    """Raised when config.toml is missing or invalid."""


class MediaError(AmbientTvError):
    """Raised when configured media cannot be used."""


class PublishError(AmbientTvError):
    """Raised when static site publishing is unsafe or fails."""
