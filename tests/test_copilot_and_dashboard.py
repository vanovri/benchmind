"""Unit tests for BenchMind v0.2.0 AI Hardware Copilot and Web Dashboard generator."""
from __future__ import annotations

import json
import os
from pathlib import Path
import pytest

import benchmind
from benchmind.agent_loop import run_autonomous_loop
from benchmind.cli import main as cli_main
from benchmind.copilot import (
    HACKATHON_TEAM_ID,
    HardwareCopilot,
    analyze_dsp_spectrum,
    analyze_uart_telemetry,
    build_probe_checklist,
    build_root_cause_hypotheses,
    build_sponsor_stack_plan,
    run_hardware_copilot,
    validate_copilot_diagnosis,
)
from benchmind.dashboard import (
    DEFAULT_DASHBOARD_PATH,
    build_dashboard_dataset,
    generate_dashboard_html,
    write_dashboard,
)
from benchmind.triage import HallucinatedEvidenceError, TriageValidationError, WithheldEvidenceViolation


def test_version_is_0_2_0():
    assert benchmind.__version__ == "0.2.0"
    report = run_autonomous_loop()
    assert report.version == "0.2.0"
    assert report.team_id == HACKATHON_TEAM_ID
    assert report.team_id == "1429535549246922"


def test_uart_and_dsp_telemetry_analyzers():
    uart_m = analyze_uart_telemetry()
    assert uart_m.total_frames_sent == 2000
    assert uart_m.valid_frames_recovered == 1997
    assert uart_m.expected_valid_frames == 1997
    assert uart_m.naive_frames_decoded == 9
    assert uart_m.sync_losses_eliminated == 1988
    assert uart_m.crc_failures_isolated == 3
    assert uart_m.zoh_gap_locks == 3
    assert uart_m.recovery_rate_pct == 100.0
    assert uart_m.estimated_baud_drift_ppm > 0.0
    assert len(uart_m.gap_anomaly_indices) == 3

    dsp_m = analyze_dsp_spectrum()
    assert dsp_m.hum_50hz_attenuation_db == 25.5
    assert dsp_m.hf_920hz_attenuation_db == 13.33
    assert dsp_m.dc_offset_drift_mv == 150.25
    assert dsp_m.filtered_rms_mv < dsp_m.unfiltered_rms_mv
    assert dsp_m.filtered_mav_mv < dsp_m.unfiltered_mav_mv
    assert dsp_m.snr_gain_db >= 15.0
    assert dsp_m.adc_clipping_detected is False
    assert dsp_m.adc_headroom_pct > 25.0
    assert dsp_m.biquad_jury_stable is True


def test_copilot_generates_hypotheses_checklist_and_sponsor_stack():
    old_bt = os.environ.pop("BASETEN_API_KEY", None)
    old_fw = os.environ.pop("FIREWORKS_API_KEY", None)
    try:
        diag_a = run_hardware_copilot()
        diag_b = run_hardware_copilot()
        assert diag_a == diag_b  # 100% deterministic offline fallback
        assert diag_a["version"] == "0.2.0"
        assert diag_a["team_id"] == "1429535549246922"
        assert diag_a["offline"] is True
        assert diag_a["hardwareEvaluated"] is False
        assert diag_a["overall_health_score"] == 100.0

        hypotheses = diag_a["root_cause_hypotheses"]
        assert len(hypotheses) == 4
        for h in hypotheses:
            assert 0.0 <= h["severity_score"] <= 10.0
            assert h["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
            assert len(h["evidence_ids"]) >= 1
            assert len(h["finding_ids"]) >= 1

        checklist = diag_a["probe_checklist"]
        assert len(checklist) == 4
        categories = " ".join(c["category"] + " " + c["action"] for c in checklist).lower()
        assert "pa0" in categories and "adc" in categories
        assert "ground" in categories
        assert "dma" in categories and "circular" in categories
        assert "baud" in categories

        sponsor = diag_a["sponsor_stack_plan"]
        assert sponsor["team_id"] == "1429535549246922"
        pillars = sponsor["pillars"]
        assert set(pillars.keys()) == {"meta_llama", "baseten", "fireworks_ai", "modal"}
    finally:
        if old_bt is not None:
            os.environ["BASETEN_API_KEY"] = old_bt
        if old_fw is not None:
            os.environ["FIREWORKS_API_KEY"] = old_fw


def test_copilot_respects_withheld_evidence_and_rejects_hallucinations():
    diag = run_hardware_copilot(withheld_evidence="E4")
    for h in diag["root_cause_hypotheses"]:
        assert "E4" not in h["evidence_ids"]
    validate_copilot_diagnosis(diag, withheld_evidence="E4")

    # Mutate with hallucinated evidence E99 -> must raise
    bad = json.loads(json.dumps(diag))
    bad["root_cause_hypotheses"][0]["evidence_ids"].append("E99")
    with pytest.raises((HallucinatedEvidenceError, TriageValidationError)):
        validate_copilot_diagnosis(bad)

    # Mutate with hardwareEvaluated=True -> must raise
    bad_hw = json.loads(json.dumps(diag))
    bad_hw["hardwareEvaluated"] = True
    with pytest.raises(TriageValidationError):
        validate_copilot_diagnosis(bad_hw)


def test_dashboard_generator_outputs_self_contained_html(tmp_path: Path):
    dataset = build_dashboard_dataset()
    assert dataset["version"] == "0.2.0"
    assert dataset["team_id"] == "1429535549246922"
    assert dataset["spectrum"]["hum_50hz_attenuation_db"] == 25.5
    assert dataset["uart_inspector"]["valid_frames_recovered"] == 1997
    assert dataset["uart_inspector"]["expected_valid_frames"] == 1997
    assert len(dataset["oscilloscope"]["raw_mv"]) == 240
    assert len(dataset["oscilloscope"]["filtered_mv"]) == 240

    out_file = tmp_path / "index.html"
    written = write_dashboard(out_file)
    assert written == out_file
    assert out_file.exists()
    html = out_file.read_text(encoding="utf-8")
    assert "BenchMind v0.2.0" in html
    assert "1429535549246922" in html
    assert "1997/1997" in html
    assert "25.5 dB" in html
    assert "Interactive Byte-Stream Fault Injection Simulator" in html
    assert "Meta Llama" in html and "Baseten" in html and "Fireworks AI" in html and "Modal" in html


def test_cli_flags_output_and_dashboard(tmp_path: Path):
    json_out = tmp_path / "verification.json"
    html_out = tmp_path / "dashboard.html"
    rc = cli_main(["--output", str(json_out), "--dashboard", str(html_out)])
    assert rc == 0
    assert json_out.exists()
    assert html_out.exists()
    loaded = json.loads(json_out.read_text(encoding="utf-8"))
    assert loaded["version"] == "0.2.0"
    assert loaded["team_id"] == "1429535549246922"
    assert loaded["copilot"]["overall_health_score"] == 100.0
    assert loaded["hardwareEvaluated"] is False

    copilot_json = tmp_path / "copilot.json"
    rc2 = cli_main(["--copilot-only", "--output", str(copilot_json)])
    assert rc2 == 0
    cp = json.loads(copilot_json.read_text(encoding="utf-8"))
    assert cp["team_id"] == "1429535549246922"
    assert len(cp["root_cause_hypotheses"]) == 4
