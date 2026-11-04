from benchmind.agent_loop import run_autonomous_loop
from benchmind.telemetry import generate_stream
from benchmind.dsp_repair import parse_uart_naive, parse_uart_repaired


def test_uart_resynchronization_recovers_all_valid_frames():
    stream = generate_stream(duration_s=0.25, inject_bad_crc_at=(5, 42))
    naive_ok, _ = parse_uart_naive(stream.uart_chunks)
    rep_ok, rep_bad_crc = parse_uart_repaired(stream.uart_chunks)
    assert len(naive_ok) < len(rep_ok)
    assert len(rep_ok) == 1000 - 2
    assert rep_bad_crc == 2


def test_autonomous_loop_passes_sandbox_gate():
    report = run_autonomous_loop()
    assert report.sandbox_gate_passed is True
    assert report.repaired_verification["uart_recovery_rate_pct"] == 100.0
    assert report.improvement_summary["hum_50hz_attenuation_db"] >= 18.0
    assert len(report.evidence_sha256) == 64
