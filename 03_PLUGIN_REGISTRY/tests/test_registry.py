from __future__ import annotations

import pytest

from _03_plugin_registry import (
    DuplicatePluginError,
    ForensicRegistry,
    InvalidNameError,
    InvalidSchemaError,
    RegistryError,
    UnknownPluginError,
)


@pytest.fixture(autouse=True)
def isolated_registry():
    """Keep every test independent from the class-level registry state."""
    before = ForensicRegistry.snapshot()
    yield before
    ForensicRegistry.restore(before)


class BurstConfig:
    pass


class BurstSymptom:
    pass


class OtherConfig:
    pass


class OtherSymptom:
    pass


class TransitionEntropyScorer:
    pass


class OtherScorer:
    pass


def register_burst() -> None:
    ForensicRegistry.register_symptom("burst", BurstConfig)(BurstSymptom)


def test_register_symptom_stores_class_and_schema():
    decorated = ForensicRegistry.register_symptom("burst", BurstConfig)(BurstSymptom)

    assert decorated is BurstSymptom
    assert ForensicRegistry.get_symptom("burst") == (BurstSymptom, BurstConfig)
    assert ForensicRegistry.SYMPTOMS["burst"] is BurstSymptom
    assert ForensicRegistry.SYMPTOMS_CONFIGS["burst"] is BurstConfig


def test_register_pattern_scorer_stores_class():
    decorated = ForensicRegistry.register_pattern_scorer("transition_entropy")(TransitionEntropyScorer)

    assert decorated is TransitionEntropyScorer
    assert ForensicRegistry.get_pattern_scorer("transition_entropy") is TransitionEntropyScorer


def test_register_symptom_is_idempotent_for_same_class_and_schema():
    register_burst()
    after_first = ForensicRegistry.snapshot()

    ForensicRegistry.register_symptom("burst", BurstConfig)(BurstSymptom)

    assert ForensicRegistry.snapshot() == after_first
    assert len(ForensicRegistry.SYMPTOMS) == 1


def test_register_pattern_scorer_is_idempotent_for_same_class():
    ForensicRegistry.register_pattern_scorer("transition_entropy")(TransitionEntropyScorer)
    after_first = ForensicRegistry.snapshot()

    ForensicRegistry.register_pattern_scorer("transition_entropy")(TransitionEntropyScorer)

    assert ForensicRegistry.snapshot() == after_first
    assert len(ForensicRegistry.PATTERN_SCORERS) == 1


def test_duplicate_symptom_name_with_different_class_raises_and_keeps_state():
    register_burst()
    before = ForensicRegistry.snapshot()

    with pytest.raises(DuplicatePluginError) as excinfo:
        ForensicRegistry.register_symptom("burst", BurstConfig)(OtherSymptom)

    assert str(excinfo.value) == "burst"
    assert ForensicRegistry.snapshot() == before
    assert ForensicRegistry.get_symptom("burst") == (BurstSymptom, BurstConfig)


def test_duplicate_symptom_name_with_different_schema_raises_at_factory_and_keeps_state():
    register_burst()
    before = ForensicRegistry.snapshot()

    with pytest.raises(DuplicatePluginError) as excinfo:
        ForensicRegistry.register_symptom("burst", OtherConfig)

    assert str(excinfo.value) == "burst"
    assert ForensicRegistry.snapshot() == before


def test_duplicate_symptom_name_with_same_class_but_different_schema_raises():
    register_burst()
    before = ForensicRegistry.snapshot()

    with pytest.raises(DuplicatePluginError):
        ForensicRegistry.register_symptom("burst", OtherConfig)(BurstSymptom)

    assert ForensicRegistry.snapshot() == before


def test_duplicate_scorer_name_with_different_class_raises_and_keeps_state():
    ForensicRegistry.register_pattern_scorer("transition_entropy")(TransitionEntropyScorer)
    before = ForensicRegistry.snapshot()

    with pytest.raises(DuplicatePluginError) as excinfo:
        ForensicRegistry.register_pattern_scorer("transition_entropy")(OtherScorer)

    assert str(excinfo.value) == "transition_entropy"
    assert ForensicRegistry.snapshot() == before
    assert ForensicRegistry.get_pattern_scorer("transition_entropy") is TransitionEntropyScorer


@pytest.mark.parametrize(
    "name",
    [
        None,
        42,
        b"burst",
        "",
        "a",
        "Burst",
        "1burst",
        "has-dash",
        "with space",
        " trailing",
        "trailing ",
        "b" * 65,
    ],
)
def test_invalid_names_raise_and_leave_state_untouched(name):
    before = ForensicRegistry.snapshot()

    with pytest.raises(InvalidNameError) as excinfo:
        ForensicRegistry.register_symptom(name, BurstConfig)

    if isinstance(name, str):
        assert name in str(excinfo.value)
    assert str(excinfo.value) != ""
    assert ForensicRegistry.snapshot() == before


@pytest.mark.parametrize("name", ["ab", "a" * 64, "planned_2"])
def test_valid_name_boundaries_are_accepted(name):
    ForensicRegistry.register_symptom(name, BurstConfig)(BurstSymptom)

    assert ForensicRegistry.get_symptom(name) == (BurstSymptom, BurstConfig)


@pytest.mark.parametrize("schema", [None, object(), "BurstConfig", len, 42])
def test_config_schema_must_be_a_class(schema):
    before = ForensicRegistry.snapshot()

    with pytest.raises(InvalidSchemaError) as excinfo:
        ForensicRegistry.register_symptom("burst", schema)

    assert type(schema).__name__ in str(excinfo.value)
    assert ForensicRegistry.snapshot() == before


def test_decorator_rejects_non_class_and_reports_received_type():
    before = ForensicRegistry.snapshot()

    with pytest.raises(InvalidSchemaError) as excinfo:
        ForensicRegistry.register_symptom("burst", BurstConfig)(42)

    assert "int" in str(excinfo.value)
    assert ForensicRegistry.snapshot() == before
    assert "burst" not in ForensicRegistry.SYMPTOMS


def test_pattern_scorer_decorator_rejects_non_class():
    before = ForensicRegistry.snapshot()

    with pytest.raises(InvalidSchemaError) as excinfo:
        ForensicRegistry.register_pattern_scorer("transition_entropy")(None)

    assert "NoneType" in str(excinfo.value)
    assert ForensicRegistry.snapshot() == before


def test_unknown_symptom_lookup_raises_with_name():
    with pytest.raises(UnknownPluginError) as excinfo:
        ForensicRegistry.get_symptom("missing")

    assert str(excinfo.value) == "missing"


def test_unknown_scorer_lookup_raises_with_name():
    with pytest.raises(UnknownPluginError) as excinfo:
        ForensicRegistry.get_pattern_scorer("missing")

    assert str(excinfo.value) == "missing"


def test_lookup_validates_name_before_dict_access():
    with pytest.raises(InvalidNameError):
        ForensicRegistry.get_symptom("Burst")
    with pytest.raises(InvalidNameError):
        ForensicRegistry.get_pattern_scorer("")


def test_symptom_and_scorer_share_a_name_without_overwriting_each_other():
    ForensicRegistry.register_symptom("burst", BurstConfig)(BurstSymptom)
    ForensicRegistry.register_pattern_scorer("burst")(TransitionEntropyScorer)

    assert ForensicRegistry.get_symptom("burst") == (BurstSymptom, BurstConfig)
    assert ForensicRegistry.get_pattern_scorer("burst") is TransitionEntropyScorer


def test_snapshot_returns_fresh_shallow_copies():
    register_burst()
    first = ForensicRegistry.snapshot()
    second = ForensicRegistry.snapshot()

    assert first is not second
    assert first["symptoms"] is not second["symptoms"]
    assert first == second

    first["symptoms"].clear()
    first["configs"]["burst"] = OtherConfig
    first["scorers"]["injected"] = OtherScorer

    assert ForensicRegistry.get_symptom("burst") == (BurstSymptom, BurstConfig)
    assert "injected" not in ForensicRegistry.PATTERN_SCORERS


def test_restore_returns_registry_to_snapshotted_state():
    register_burst()
    before = ForensicRegistry.snapshot()
    ForensicRegistry.register_pattern_scorer("transition_entropy")(TransitionEntropyScorer)
    ForensicRegistry.register_symptom("other", OtherConfig)(OtherSymptom)

    ForensicRegistry.restore(before)

    assert ForensicRegistry.snapshot() == before
    assert "transition_entropy" not in ForensicRegistry.PATTERN_SCORERS
    assert "other" not in ForensicRegistry.SYMPTOMS
    assert ForensicRegistry.get_symptom("burst") == (BurstSymptom, BurstConfig)


def test_restore_does_not_keep_references_to_caller_state():
    state = {
        "symptoms": {"burst": BurstSymptom},
        "configs": {"burst": BurstConfig},
        "scorers": {"transition_entropy": TransitionEntropyScorer},
    }

    ForensicRegistry.restore(state)
    state["symptoms"]["other"] = OtherSymptom
    state["symptoms"].clear()

    assert ForensicRegistry.get_symptom("burst") == (BurstSymptom, BurstConfig)
    assert "other" not in ForensicRegistry.SYMPTOMS


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"symptoms": {}, "configs": {}},
        {"symptoms": {}, "scorers": {}},
        {"configs": {}, "scorers": {}},
        None,
        ["symptoms", "configs", "scorers"],
    ],
)
def test_restore_rejects_incomplete_state(state):
    with pytest.raises(ValueError):
        ForensicRegistry.restore(state)


def test_clear_empties_every_registry_dict_in_place():
    register_burst()
    ForensicRegistry.register_pattern_scorer("transition_entropy")(TransitionEntropyScorer)
    symptoms = ForensicRegistry.SYMPTOMS
    configs = ForensicRegistry.SYMPTOMS_CONFIGS
    scorers = ForensicRegistry.PATTERN_SCORERS

    ForensicRegistry.clear()

    assert ForensicRegistry.snapshot() == {"symptoms": {}, "configs": {}, "scorers": {}}
    assert ForensicRegistry.SYMPTOMS is symptoms
    assert ForensicRegistry.SYMPTOMS_CONFIGS is configs
    assert ForensicRegistry.PATTERN_SCORERS is scorers


def test_clear_and_restore_keep_registry_dict_identity():
    state = ForensicRegistry.snapshot()
    symptoms = ForensicRegistry.SYMPTOMS

    ForensicRegistry.restore(state)

    assert ForensicRegistry.SYMPTOMS is symptoms


def test_all_registry_errors_share_a_common_base():
    assert issubclass(InvalidNameError, RegistryError)
    assert issubclass(InvalidSchemaError, RegistryError)
    assert issubclass(DuplicatePluginError, RegistryError)
    assert issubclass(UnknownPluginError, RegistryError)


def test_registration_order_does_not_affect_lookup():
    ForensicRegistry.register_symptom("second", OtherConfig)(OtherSymptom)
    ForensicRegistry.register_symptom("burst", BurstConfig)(BurstSymptom)

    assert ForensicRegistry.get_symptom("burst") == (BurstSymptom, BurstConfig)
    assert ForensicRegistry.get_symptom("second") == (OtherSymptom, OtherConfig)
