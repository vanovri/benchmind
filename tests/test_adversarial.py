"""Adversarial UART & Biquad DF2T tests — corrupted sync, burst CRC, stability."""
import math
import struct
import zlib
import pytest
from benchmind.telemetry import FRAME_MAGIC, generate_stream, pack_frame, SAMPLE_RATE_HZ
from benchmind.dsp_repair import (
    BiquadDF2T,
    design_butterworth_hpf,
    design_butterworth_lpf,
    design_notch_50hz,
    parse_uart_naive,
    parse_uart_repaired,
    compute_dft_bin_db,
    compute_rms_mav,
    validate_biquad_stability,
    check_biquad_impulse_stability,
)
from benchmind.agent_loop import run_autonomous_loop

def _make_chunks_from_bytes(raw: bytes, pattern=(5, 3, 11)):
    chunks = []
    idx = pat = 0
    while idx < len(raw):
        step = pattern[pat % len(pattern)]
        chunks.append(raw[idx: idx+step])
        idx += step
        pat += 1
    return chunks

def test_corrupted_uart_sync_word_not_decoded_as_frame():
    good_payload = struct.pack("<BH", 10, 1234)
    good_crc = zlib.crc32(good_payload) & 0xFFFFFFFF
    good_frame = FRAME_MAGIC + good_payload + struct.pack("<I", good_crc)
    corrupted_sync_1 = b"\xAA\x54" + good_payload + struct.pack("<I", good_crc)
    corrupted_sync_2 = b"\xAB\x55" + good_payload + struct.pack("<I", good_crc)
    corrupted_sync_3 = b"\xFF\xFF" + good_payload + struct.pack("<I", good_crc)
    raw = corrupted_sync_1 + good_frame + corrupted_sync_2 + good_frame + corrupted_sync_3 + good_frame
    chunks = _make_chunks_from_bytes(raw)
    decoded, rejected = parse_uart_repaired(chunks)
    assert len(decoded) == 3
    assert all(seq == 10 for seq, _ in decoded)
    naive, _ = parse_uart_naive(chunks)
    assert len(naive) <= 1

def test_corrupted_uart_sync_word_split_across_chunks():
    seq, adc = 42, 2048
    frame = pack_frame(seq, adc)
    raw = frame + frame
    chunks = [raw[0:1], raw[1:5], raw[5:9], raw[9:10], raw[10:]]
    decoded, rejected = parse_uart_repaired(chunks)
    assert len(decoded) == 2
    assert rejected == 0

def test_burst_crc32_bitflips_isolated_and_all_valid_recovered():
    n = 100
    inject = tuple(range(10, 15))
    raw_stream = bytearray()
    expected_valid = []
    for i in range(n):
        adc = 2048
        frame = bytearray(pack_frame(i % 256, adc))
        if i in inject:
            frame[-1] ^= 0xFF
            frame[-2] ^= 0x0F
            raw_stream.extend(frame)
        else:
            raw_stream.extend(frame)
            expected_valid.append((i % 256, adc))
    chunks = _make_chunks_from_bytes(bytes(raw_stream), pattern=(7,2,13))
    decoded, rejected = parse_uart_repaired(chunks)
    assert rejected == len(inject)
    assert len(decoded) == len(expected_valid)
    assert decoded == expected_valid

def test_fragmented_stream_recovery_with_embedded_sync_bytes():
    raw = bytearray()
    frames_expected = []
    for seq in range(20):
        adc = 0x55AA if seq % 5 == 0 else 1000 + seq
        frame = pack_frame(seq, adc)
        raw.extend(frame)
        frames_expected.append((seq, adc & 0xFFFF))
    chunks = _make_chunks_from_bytes(bytes(raw), pattern=(4,9,2))
    decoded, rejected = parse_uart_repaired(chunks)
    assert len(decoded) == len(frames_expected)
    assert rejected == 0
    assert decoded == frames_expected

def test_biquad_df2t_stability_all_filters():
    hpf = design_butterworth_hpf(20.0)
    lpf = design_butterworth_lpf(500.0)
    notch = design_notch_50hz(50.0, q=30.0)
    notch_q12 = design_notch_50hz(50.0, q=12.0)
    for f in (hpf, lpf, notch, notch_q12):
        assert f.is_stable()
        assert validate_biquad_stability(f) is True
        assert check_biquad_impulse_stability(f, n=1000) is True
        assert abs(f.a2) < 1.0
        assert abs(f.a1) < 1.0 + f.a2
        assert f.pole_radius() < 1.0

def test_biquad_impulse_response_bounded_and_not_diverging():
    hpf = design_butterworth_hpf(20.0)
    lpf = design_butterworth_lpf(500.0)
    notch = design_notch_50hz(50.0, q=30.0)
    for bq in (hpf, lpf, notch):
        bq.reset()
        outs = []
        outs.append(bq.process(1.0))
        for _ in range(500):
            outs.append(bq.process(0.0))
        assert max(abs(x) for x in outs) < 2.0
        assert abs(outs[-1]) < 0.01

def test_biquad_unstable_detection():
    unstable1 = BiquadDF2T(b0=1, b1=0, b2=0, a1=0.5, a2=1.0)
    unstable2 = BiquadDF2T(b0=1, b1=0, b2=0, a1=1.9, a2=0.8)
    assert unstable1.is_stable() is False
    assert unstable2.is_stable() is False
    assert validate_biquad_stability(unstable1) is False
    assert validate_biquad_stability(unstable2) is False
    with pytest.raises(ValueError):
        unstable1.validate_stability()
    stable = design_notch_50hz(50.0, q=30.0)
    stable.validate_stability()

def test_frequency_response_notch_attenuates_50hz():
    notch = design_notch_50hz(50.0, q=30.0)
    resp_50 = notch.frequency_response_db(50.0)
    resp_100 = notch.frequency_response_db(100.0)
    assert resp_50 < -15.0, f"notch at 50Hz should be < -15dB, got {resp_50}"
    assert resp_100 > -3.0, f"notch should pass 100Hz, got {resp_100}"
    report = run_autonomous_loop()
    assert report.improvement_summary["hum_50hz_attenuation_db"] >= 18.0

def test_high_freq_attenuation_sanity():
    lpf = design_butterworth_lpf(500.0)
    resp_920 = lpf.frequency_response_db(920.0)
    resp_100 = lpf.frequency_response_db(100.0)
    assert resp_920 < resp_100 - 3.0, f"LPF should attenuate 920Hz more than 100Hz: {resp_920} vs {resp_100}"
    stream = generate_stream()
    from benchmind.agent_loop import reconstruct_phase_locked_samples
    from benchmind.dsp_repair import parse_uart_repaired
    rep_frames, _ = parse_uart_repaired(stream.uart_chunks)
    rec_mv, _ = reconstruct_phase_locked_samples(rep_frames)
    dc = sum(rec_mv[:400]) / 400
    hpf = design_butterworth_hpf(20.0)
    lpf2 = design_butterworth_lpf(500.0)
    notch2 = design_notch_50hz(50.0, q=12.0)
    filtered = []
    for x in rec_mv:
        y = hpf.process(x - dc)
        y = lpf2.process(y)
        y = notch2.process(y)
        filtered.append(y)
    steady = filtered[400:]
    hf_before = compute_dft_bin_db(stream.corrupted_mv, 920.0)
    hf_after = compute_dft_bin_db(steady, 920.0)
    assert hf_before - hf_after >= 10.0, f"HF attenuation should be >=10dB, got {hf_before - hf_after}"

def test_hardware_evaluated_explicit_false_in_report():
    report = run_autonomous_loop()
    assert hasattr(report, "hardwareEvaluated")
    assert report.hardwareEvaluated is False
    # Also check triage has hardwareEvaluated false
    assert report.triage is not None
    assert report.triage["hardwareEvaluated"] is False
    assert report.triage["hardware_evaluated"] is False

def test_report_contains_triage_adapter_info():
    report = run_autonomous_loop()
    assert report.triage_adapter is not None
    assert report.triage_adapter["provider"] == "baseten"
    assert report.triage_adapter["base_url"] == "https://inference.baseten.co/v1"
    assert report.triage_adapter["model"] == "meta-models/muse-spark-open-1026"

def test_generate_stream_burst_crc_with_stray_noise_byte():
    # Existing generate_stream injects stray 0xFE before corrupted frames
    stream = generate_stream(duration_s=0.5, inject_bad_crc_at=(17,63,142))
    rep_frames, rep_bad = parse_uart_repaired(stream.uart_chunks)
    assert rep_bad == 3
    assert len(rep_frames) == stream.injected_faults["total_frames_sent"] - 3
    # Ensure naive fails
    naive_frames, _ = parse_uart_naive(stream.uart_chunks)
    assert len(naive_frames) < len(rep_frames)
    assert len(naive_frames) < 50

