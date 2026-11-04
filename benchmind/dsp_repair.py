"""Baseline vs Autonomous Synthesized Biquad DSP + Buffered CRC-32 UART Parser."""
from __future__ import annotations
import math
import struct
import zlib
from dataclasses import dataclass
from typing import List, Tuple
from .telemetry import FRAME_MAGIC, SAMPLE_RATE_HZ


@dataclass
class BiquadDF2T:
    """Direct Form II Transposed 2nd-order IIR Biquad filter with stability checks."""
    b0: float
    b1: float
    b2: float
    a1: float
    a2: float
    s1: float = 0.0
    s2: float = 0.0

    def process(self, x: float) -> float:
        y = self.b0 * x + self.s1
        self.s1 = self.b1 * x - self.a1 * y + self.s2
        self.s2 = self.b2 * x - self.a2 * y
        return y

    def reset(self) -> None:
        self.s1 = 0.0
        self.s2 = 0.0

    def is_stable(self) -> bool:
        """Jury stability criterion for 2nd-order IIR: poles inside unit circle."""
        # Denominator: 1 + a1*z^-1 + a2*z^-2 => polynomial z^2 + a1*z + a2
        # Stable iff |a2| < 1 and |a1| < 1 + a2
        if abs(self.a2) >= 1.0:
            return False
        if abs(self.a1) >= 1.0 + self.a2:
            return False
        return True

    def pole_radius(self) -> float:
        """Max pole magnitude (approx)."""
        disc = self.a1 * self.a1 - 4 * self.a2
        if disc >= 0:
            r1 = abs((-self.a1 + math.sqrt(disc)) / 2.0)
            r2 = abs((-self.a1 - math.sqrt(disc)) / 2.0)
            return max(r1, r2)
        else:
            return math.sqrt(abs(self.a2))

    def validate_stability(self) -> None:
        if not self.is_stable():
            raise ValueError(f"Biquad DF2T unstable: a1={self.a1}, a2={self.a2}, |a2|={abs(self.a2)}, pole_radius={self.pole_radius():.3f}")

    def frequency_response_db(self, freq_hz: float, fs: float = SAMPLE_RATE_HZ) -> float:
        """Magnitude response at freq_hz in dB (for diagnostics)."""
        w = 2.0 * math.pi * freq_hz / fs
        cos_w = math.cos(w)
        sin_w = math.sin(w)
        # z = e^{jw}
        # H(z) = (b0 + b1 z^-1 + b2 z^-2)/(1 + a1 z^-1 + a2 z^-2)
        # Use complex via math
        import cmath
        z_inv = cmath.exp(complex(0, -w))
        z_inv2 = z_inv * z_inv
        num = self.b0 + self.b1 * z_inv + self.b2 * z_inv2
        den = 1.0 + self.a1 * z_inv + self.a2 * z_inv2
        if abs(den) < 1e-12:
            return -120.0
        h = num / den
        mag = abs(h)
        return 20.0 * math.log10(max(mag, 1e-12))


def design_butterworth_hpf(fc: float = 20.0, fs: float = SAMPLE_RATE_HZ) -> BiquadDF2T:
    w0 = 2.0 * math.pi * fc / fs
    alpha = math.sin(w0) / math.sqrt(2.0)
    cos_w0 = math.cos(w0)
    b0 = (1.0 + cos_w0) / 2.0
    b1 = -(1.0 + cos_w0)
    b2 = (1.0 + cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha
    f = BiquadDF2T(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)
    f.validate_stability()
    return f


def design_butterworth_lpf(fc: float = 500.0, fs: float = SAMPLE_RATE_HZ) -> BiquadDF2T:
    w0 = 2.0 * math.pi * fc / fs
    alpha = math.sin(w0) / math.sqrt(2.0)
    cos_w0 = math.cos(w0)
    b0 = (1.0 - cos_w0) / 2.0
    b1 = 1.0 - cos_w0
    b2 = (1.0 - cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha
    f = BiquadDF2T(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)
    f.validate_stability()
    return f


def design_notch_50hz(f0: float = 50.0, q: float = 30.0, fs: float = SAMPLE_RATE_HZ) -> BiquadDF2T:
    w0 = 2.0 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2.0 * q)
    cos_w0 = math.cos(w0)
    b0 = 1.0
    b1 = -2.0 * cos_w0
    b2 = 1.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha
    f = BiquadDF2T(b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)
    f.validate_stability()
    return f


def validate_biquad_stability(bq: BiquadDF2T) -> bool:
    """Validate Biquad DF2T stability (Jury criterion)."""
    return bq.is_stable()

def check_biquad_impulse_stability(bq: BiquadDF2T, n: int = 500) -> bool:
    """Impulse response must stay bounded (no divergence)."""
    bq.reset()
    y = bq.process(1.0)
    max_abs = abs(y)
    for _ in range(n - 1):
        y = bq.process(0.0)
        max_abs = max(max_abs, abs(y))
        if abs(y) > 1e6 or math.isnan(y) or math.isinf(y):
            return False
    return max_abs < 1e3


def parse_uart_naive(chunks: List[bytes]) -> Tuple[List[Tuple[int, int]], int]:
    """Faulty baseline parser: assumes each read chunk starts on a 9-byte frame boundary."""
    decoded: List[Tuple[int, int]] = []
    rejected = 0
    for chunk in chunks:
        if len(chunk) >= 9 and chunk[:2] == FRAME_MAGIC:
            seq, adc = struct.unpack("<BH", chunk[2:5])
            crc_rx = struct.unpack("<I", chunk[5:9])[0]
            if (zlib.crc32(chunk[2:5]) & 0xFFFFFFFF) == crc_rx:
                decoded.append((seq, adc))
            else:
                rejected += 1
        else:
            rejected += 1
    return decoded, rejected


def parse_uart_repaired(chunks: List[bytes]) -> Tuple[List[Tuple[int, int]], int]:
    """Synthesized buffered state-machine parser: resynchronizes byte-by-byte on AA 55 + CRC-32."""
    buf = bytearray()
    decoded: List[Tuple[int, int]] = []
    rejected_crc = 0
    for chunk in chunks:
        buf.extend(chunk)
        while len(buf) >= 9:
            pos = buf.find(FRAME_MAGIC)
            if pos < 0:
                # Keep last byte if it could be start of AA 55
                if buf[-1:] == b"\xAA":
                    buf[:] = b"\xAA"
                else:
                    buf.clear()
                break
            if pos > 0:
                del buf[:pos]
            if len(buf) < 9:
                break
            payload = bytes(buf[2:5])
            crc_rx = struct.unpack("<I", buf[5:9])[0]
            crc_calc = zlib.crc32(payload) & 0xFFFFFFFF
            if crc_rx == crc_calc:
                seq, adc = struct.unpack("<BH", payload)
                decoded.append((seq, adc))
                del buf[:9]
            else:
                rejected_crc += 1
                del buf[:2]  # Advance past false/corrupted header and resync
    return decoded, rejected_crc


def compute_dft_bin_db(samples: List[float], freq_hz: float, fs: float = SAMPLE_RATE_HZ) -> float:
    n = len(samples)
    if n == 0:
        return -120.0
    re_sum = 0.0
    im_sum = 0.0
    for i, x in enumerate(samples):
        angle = -2.0 * math.pi * freq_hz * i / fs
        re_sum += x * math.cos(angle)
        im_sum += x * math.sin(angle)
    mag = math.hypot(re_sum, im_sum) * (2.0 / n)
    return 20.0 * math.log10(max(mag, 1e-9))


def compute_rms_mav(samples: List[float]) -> Tuple[float, float]:
    if not samples:
        return 0.0, 0.0
    rms = math.sqrt(sum(x * x for x in samples) / len(samples))
    mav = sum(abs(x) for x in samples) / len(samples)
    return round(rms, 4), round(mav, 4)
