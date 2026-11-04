"""Synthetic 4 kHz 12-bit ADC + framed UART telemetry generator and fault injector."""
from __future__ import annotations
import math
import struct
import zlib
from dataclasses import dataclass
from typing import List, Tuple

SAMPLE_RATE_HZ = 4000
FRAME_MAGIC = b"\xAA\x55"


@dataclass(frozen=True)
class TelemetryStream:
    sample_rate_hz: int
    clean_mv: List[float]
    corrupted_mv: List[float]
    adc_counts: List[int]
    uart_chunks: List[bytes]
    injected_faults: dict


def pack_frame(seq: int, adc_raw: int) -> bytes:
    payload = struct.pack("<BH", seq & 0xFF, adc_raw & 0xFFFF)
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return FRAME_MAGIC + payload + struct.pack("<I", crc)


def generate_stream(
    duration_s: float = 0.5,
    hum_50hz_mv: float = 28.0,
    dc_offset_mv: float = 150.0,
    inject_bad_crc_at: Tuple[int, ...] = (17, 63, 142),
    chunk_pattern: Tuple[int, ...] = (3, 7, 11, 5, 19),
) -> TelemetryStream:
    n = int(duration_s * SAMPLE_RATE_HZ)
    clean_mv: List[float] = []
    corrupted_mv: List[float] = []
    adc_counts: List[int] = []
    raw_stream = bytearray()

    for i in range(n):
        t = i / SAMPLE_RATE_HZ
        # Synthetic burst signal (100 Hz + 180 Hz in active band 20-500 Hz)
        envelope = 1.0 if 0.15 <= (t % 0.5) <= 0.42 else 0.15
        sig = envelope * (32.0 * math.sin(2.0 * math.pi * 95.0 * t) + 18.0 * math.sin(2.0 * math.pi * 165.0 * t))
        hum = hum_50hz_mv * math.sin(2.0 * math.pi * 50.0 * t)
        high_freq_noise = 9.5 * math.sin(2.0 * math.pi * 920.0 * t)
        noisy = sig + hum + high_freq_noise + dc_offset_mv

        clean_mv.append(sig)
        corrupted_mv.append(noisy)

        # Map mV around 1650 mV mid-scale into 12-bit ADC (0..4095, 3300 mV full scale)
        mv_total = 1650.0 + noisy
        adc = int(round((mv_total / 3300.0) * 4095.0))
        adc_clamped = max(0, min(4095, adc))
        adc_counts.append(adc_clamped)

        frame = bytearray(pack_frame(i % 256, adc_clamped))
        if i in inject_bad_crc_at:
            frame[-1] ^= 0xFF  # Corrupt CRC byte
            raw_stream.extend(b"\xFE")  # Prepend stray noise byte before frame
        raw_stream.extend(frame)

    # Split byte stream into uneven fragmented chunks to break naive unbuffered parsers
    uart_chunks: List[bytes] = []
    idx = 0
    pat_idx = 0
    while idx < len(raw_stream):
        step = chunk_pattern[pat_idx % len(chunk_pattern)]
        uart_chunks.append(bytes(raw_stream[idx : idx + step]))
        idx += step
        pat_idx += 1

    return TelemetryStream(
        sample_rate_hz=SAMPLE_RATE_HZ,
        clean_mv=clean_mv,
        corrupted_mv=corrupted_mv,
        adc_counts=adc_counts,
        uart_chunks=uart_chunks,
        injected_faults={
            "total_frames_sent": n,
            "hum_50hz_mv": hum_50hz_mv,
            "dc_offset_mv": dc_offset_mv,
            "corrupted_crc_frames": len(inject_bad_crc_at),
            "fragmented_uart_chunks": len(uart_chunks),
        },
    )
