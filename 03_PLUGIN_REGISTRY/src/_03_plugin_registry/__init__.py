"""Forensic plugin registry: symptom and pattern-scorer decorators."""

from .forensic_registry import (
    DuplicatePluginError,
    ForensicRegistry,
    InvalidNameError,
    InvalidSchemaError,
    RegistryError,
    UnknownPluginError,
)

__all__ = [
    "DuplicatePluginError",
    "ForensicRegistry",
    "InvalidNameError",
    "InvalidSchemaError",
    "RegistryError",
    "UnknownPluginError",
]


def main() -> None:
    print("Hello from 03-plugin-registry!")
