import re
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

T = TypeVar("T", bound=type)

_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]{1,63}")


class RegistryError(Exception):
    """Base class for every registry error."""


class InvalidNameError(RegistryError):
    """Raised when a plugin name violates the naming contract."""

    def __init__(self, name: Any) -> None:
        super().__init__(f"invalid name: {name!r}")
        self.name = name


class InvalidSchemaError(RegistryError):
    """Raised when a value that must be a class is not a class."""

    def __init__(self, received: Any) -> None:
        super().__init__(f"expected a class, got {type(received).__name__}")
        self.received = received


class DuplicatePluginError(RegistryError):
    """Raised when a name is already registered for a different plugin."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class UnknownPluginError(RegistryError):
    """Raised when a plugin name has not been registered."""

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class ForensicRegistry:
    SYMPTOMS: dict[str, type] = {}
    SYMPTOMS_CONFIGS: dict[str, type] = {}
    PATTERN_SCORERS: dict[str, type] = {}

    @staticmethod
    def _validate_name(name: object) -> str:
        if not isinstance(name, str) or _NAME_PATTERN.fullmatch(name) is None:
            raise InvalidNameError(name)
        return name

    @staticmethod
    def _validate_class(value: object) -> type:
        if not isinstance(value, type):
            raise InvalidSchemaError(value)
        return value

    @classmethod
    def _check_symptom_conflict(cls, name: str, symptom_cls: type, config_schema: type) -> bool:
        """Return True when the exact same registration already exists."""
        existing_cls = cls.SYMPTOMS.get(name)
        existing_schema = cls.SYMPTOMS_CONFIGS.get(name)
        if existing_cls is None and existing_schema is None:
            return False
        if existing_cls is symptom_cls and existing_schema is config_schema:
            return True
        raise DuplicatePluginError(name)

    @classmethod
    def _commit_symptom(cls, name: str, symptom_cls: type, config_schema: type) -> None:
        cls.SYMPTOMS[name] = symptom_cls
        cls.SYMPTOMS_CONFIGS[name] = config_schema

    @classmethod
    def register_symptom(cls, name: str, config_schema: type) -> Callable[[T], T]:
        cls._validate_name(name)
        cls._validate_class(config_schema)

        existing_schema = cls.SYMPTOMS_CONFIGS.get(name)
        if existing_schema is not None and existing_schema is not config_schema:
            raise DuplicatePluginError(name)

        def decorator(symptom_cls: T) -> T:
            cls._validate_class(symptom_cls)
            if not cls._check_symptom_conflict(name, symptom_cls, config_schema):
                cls._commit_symptom(name, symptom_cls, config_schema)
            return symptom_cls

        return decorator

    @classmethod
    def register_pattern_scorer(cls, name: str) -> Callable[[T], T]:
        cls._validate_name(name)

        def decorator(scorer_cls: T) -> T:
            cls._validate_class(scorer_cls)
            existing = cls.PATTERN_SCORERS.get(name)
            if existing is None:
                cls.PATTERN_SCORERS[name] = scorer_cls
            elif existing is not scorer_cls:
                raise DuplicatePluginError(name)
            return scorer_cls

        return decorator

    @classmethod
    def get_symptom(cls, name: str) -> tuple[type, type]:
        cls._validate_name(name)
        symptom_cls = cls.SYMPTOMS.get(name)
        config_schema = cls.SYMPTOMS_CONFIGS.get(name)
        if symptom_cls is None or config_schema is None:
            raise UnknownPluginError(name)
        return symptom_cls, config_schema

    @classmethod
    def get_pattern_scorer(cls, name: str) -> type:
        cls._validate_name(name)
        scorer_cls = cls.PATTERN_SCORERS.get(name)
        if scorer_cls is None:
            raise UnknownPluginError(name)
        return scorer_cls

    @classmethod
    def snapshot(cls) -> dict[str, dict[str, type]]:
        return {
            "symptoms": dict(cls.SYMPTOMS),
            "configs": dict(cls.SYMPTOMS_CONFIGS),
            "scorers": dict(cls.PATTERN_SCORERS),
        }

    @classmethod
    def restore(cls, state: dict[str, dict[str, type]]) -> None:
        if not isinstance(state, Mapping):
            raise ValueError("state must be a mapping with 'symptoms', 'configs' and 'scorers' keys")

        keys = ("symptoms", "configs", "scorers")
        missing = [key for key in keys if key not in state]
        if missing:
            raise ValueError(f"state is missing required keys: {', '.join(missing)}")

        symptoms = dict(state["symptoms"])
        configs = dict(state["configs"])
        scorers = dict(state["scorers"])

        cls.clear()
        cls.SYMPTOMS.update(symptoms)
        cls.SYMPTOMS_CONFIGS.update(configs)
        cls.PATTERN_SCORERS.update(scorers)

    @classmethod
    def clear(cls) -> None:
        cls.SYMPTOMS.clear()
        cls.SYMPTOMS_CONFIGS.clear()
        cls.PATTERN_SCORERS.clear()

