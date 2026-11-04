"""BenchMind Triage Adapter — unit + adversarial validator tests (Baseten Muse Spark Open)."""
import os
import struct
import zlib
import pytest
from benchmind.triage import (
    BASETEN_API_URL,
    BASETEN_BASE_URL,
    BASETEN_MODEL_ID,
    BASETEN_MODEL,
    ALLOWED_EVIDENCE_IDS,
    ALLOWED_FINDING_IDS,
    TriageValidationError,
    HallucinatedEvidenceError,
    HallucinatedFindingError,
    WithheldEvidenceViolation,
    validate_evidence_ids,
    validate_finding_ids,
    validate_hardware_evaluated,
    validate_triage_response,
    validate_triage_schema,
    deterministic_offline_triage,
    MuseSparkOpenTriageAdapter,
    BasetenMuseSparkClient,
    get_baseten_api_key,
)
import benchmind.muse_spark  # noqa: F401
import benchmind.baseten_adapter  # noqa: F401

def _valid_triage_payload(overrides=None):
    base = {
        "model": BASETEN_MODEL_ID,
        "evidence_ids": ["E1", "E2", "E3"],
        "evidenceIds": ["E1", "E2", "E3"],
        "finding_ids": ["F1", "F2"],
        "findingIds": ["F1", "F2"],
        "diagnostics": {
            "uart_crc32_validated": True,
            "biquad_df2t_validated": True,
            "uart_recovery_rate_pct": 100.0,
            "hum_50hz_attenuation_db": 25.5,
        },
        "hardwareEvaluated": False,
    }
    if overrides:
        base.update(overrides)
    return base

def test_baseten_adapter_constants_and_model():
    assert BASETEN_API_URL == "https://inference.baseten.co/v1"
    assert BASETEN_BASE_URL == "https://inference.baseten.co/v1"
    assert BASETEN_MODEL_ID == "meta-models/muse-spark-open-1026"
    assert BASETEN_MODEL == "meta-models/muse-spark-open-1026"
    adapter = MuseSparkOpenTriageAdapter()
    assert adapter.base_url == "https://inference.baseten.co/v1"
    assert adapter.model == "meta-models/muse-spark-open-1026"

def test_offline_fallback_deterministic_and_hardware_false():
    diag = {"uart_crc32_validated": True, "biquad_df2t_validated": True, "uart_recovery_rate_pct": 100.0, "hum_50hz_attenuation_db": 25.5}
    a = deterministic_offline_triage(diagnostics=diag, available_evidence_ids=["E1", "E2", "E3", "E4", "E5", "E6"], withheld_evidence=None)
    b = deterministic_offline_triage(diagnostics=diag, available_evidence_ids=["E1", "E2", "E3", "E4", "E5", "E6"], withheld_evidence=None)
    assert a == b
    assert a["hardwareEvaluated"] is False
    assert a["hardware_evaluated"] is False
    assert a["model"] == "meta-models/muse-spark-open-1026"
    assert a["offline"] is True
    assert "uart_crc32_validated" in a["diagnostics"]
    assert "biquad_df2t_validated" in a["diagnostics"]

def test_offline_fallback_without_key_uses_baseten_url():
    old = os.environ.pop("BASETEN_API_KEY", None)
    old2 = os.environ.pop("BASETEN_KEY", None)
    try:
        adapter = MuseSparkOpenTriageAdapter()
        assert adapter.is_live is False
        result = adapter.triage(diagnostics={"uart_crc32_validated": True, "biquad_df2t_validated": True})
        assert result["hardwareEvaluated"] is False
        assert result["offline"] is True
        assert result["model"] == "meta-models/muse-spark-open-1026"
        validate_triage_response(result)
    finally:
        if old is not None:
            os.environ["BASETEN_API_KEY"] = old
        if old2 is not None:
            os.environ["BASETEN_KEY"] = old2

def test_validator_rejects_hallucinated_evidence_E7():
    payload = _valid_triage_payload({"evidence_ids": ["E1", "E7"], "evidenceIds": ["E1", "E7"]})
    with pytest.raises((HallucinatedEvidenceError, TriageValidationError)) as exc:
        validate_triage_response(payload)
    assert "E7" in str(exc.value) or "Hallucinated" in str(exc.value)

def test_validator_rejects_hallucinated_finding_F99():
    payload = _valid_triage_payload({"finding_ids": ["F1", "F99"], "findingIds": ["F1", "F99"]})
    with pytest.raises((HallucinatedFindingError, TriageValidationError)) as exc:
        validate_triage_response(payload)
    assert "F99" in str(exc.value) or "Hallucinated" in str(exc.value)

def test_validator_rejects_hallucinated_evidence_via_validate_evidence_ids():
    with pytest.raises(TriageValidationError):
        validate_evidence_ids(["E1", "E7", "E99"])
    with pytest.raises(TriageValidationError):
        validate_evidence_ids(["E9"])

def test_validator_rejects_hallucinated_fault_ids_via_validate_finding_ids():
    with pytest.raises(TriageValidationError):
        validate_finding_ids(["F1", "F99"])
    with pytest.raises(TriageValidationError):
        validate_finding_ids(["F9", "F10"])

def test_validator_rejects_withheld_E4_citation():
    payload = _valid_triage_payload({"evidence_ids": ["E1", "E2", "E4"], "evidenceIds": ["E1", "E2", "E4"]})
    with pytest.raises((WithheldEvidenceViolation, TriageValidationError)):
        validate_triage_response(payload, available_evidence_ids=["E1", "E2", "E3", "E5", "E6"], withheld_evidence="E4")
    diag = {"uart_crc32_validated": True, "biquad_df2t_validated": True, "hum_50hz_attenuation_db": 25.5}
    off = deterministic_offline_triage(diagnostics=diag, available_evidence_ids=["E1", "E2", "E3", "E5", "E6"], withheld_evidence="E4")
    assert "E4" not in off["evidence_ids"]
    assert "E4" not in off["evidenceIds"]

def test_validator_rejects_hardwareEvaluated_true():
    payload = _valid_triage_payload({"hardwareEvaluated": True})
    with pytest.raises(TriageValidationError) as exc:
        validate_triage_response(payload)
    assert "hardwareEvaluated" in str(exc.value) or "explicit False" in str(exc.value)
    payload2 = _valid_triage_payload()
    payload2.pop("hardwareEvaluated")
    with pytest.raises(TriageValidationError):
        validate_triage_response(payload2)
    payload3 = _valid_triage_payload({"hardwareEvaluated": "false"})
    with pytest.raises(TriageValidationError):
        validate_triage_response(payload3)
    with pytest.raises(TriageValidationError):
        validate_hardware_evaluated(True)
    with pytest.raises(TriageValidationError):
        validate_hardware_evaluated(None)
    validate_hardware_evaluated(False)

def test_validator_strict_schema_missing_required_field():
    payload = _valid_triage_payload()
    payload.pop("diagnostics")
    with pytest.raises(TriageValidationError):
        validate_triage_schema(payload)
    payload2 = _valid_triage_payload()
    payload2.pop("evidence_ids")
    payload2.pop("evidenceIds")
    with pytest.raises(TriageValidationError):
        validate_triage_schema(payload2)

def test_validator_rejects_hallucinated_fault_ids_mixed():
    with pytest.raises(TriageValidationError):
        validate_evidence_ids(["E0"])
    with pytest.raises(TriageValidationError):
        validate_finding_ids(["F0"])
    with pytest.raises(TriageValidationError):
        validate_evidence_ids(["e1"])
    validate_evidence_ids([])
    validate_finding_ids([])

def test_offline_triage_includes_uart_crc_and_dsp_validated():
    diag = {"uart_crc32_validated": True, "biquad_df2t_validated": True, "uart_recovery_rate_pct": 100.0, "hum_50hz_attenuation_db": 30.0}
    result = deterministic_offline_triage(diagnostics=diag, withheld_evidence=None)
    assert result["diagnostics"]["uart_crc32_validated"] is True
    assert result["diagnostics"]["biquad_df2t_validated"] is True
    assert result["diagnostics"]["uart_recovery_rate_pct"] == 100.0
    assert result["diagnostics"]["hum_50hz_attenuation_db"] == 30.0
    validate_triage_response(result)
    validate_triage_response(result, available_evidence_ids=["E1", "E2", "E3", "E4", "E5", "E6"], withheld_evidence=None)

def test_baseten_adapter_aliases_and_allowed_sets():
    assert ALLOWED_EVIDENCE_IDS == {"E1", "E2", "E3", "E4", "E5", "E6"}
    assert ALLOWED_FINDING_IDS == {"F1", "F2", "F3", "F4", "F5"}
    assert BasetenMuseSparkClient is MuseSparkOpenTriageAdapter
    os.environ["BASETEN_API_KEY"] = "test-key-123"
    try:
        assert get_baseten_api_key() == "test-key-123"
        adapter = MuseSparkOpenTriageAdapter()
        assert adapter.is_live is True
        result = adapter.triage(diagnostics={"uart_crc32_validated": True, "biquad_df2t_validated": True})
        assert "hardwareEvaluated" in result
        assert result["hardwareEvaluated"] is False
        validate_triage_response(result)
    finally:
        os.environ.pop("BASETEN_API_KEY", None)

