# Graph Report - benchmind  (2026-11-02)

## Corpus Check
- 9 files · ~2,050 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 38 nodes · 70 edges · 9 communities (7 shown, 2 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- run_autonomous_loop
- test_benchmind.py
- BiquadDF2T
- telemetry.py
- agent_loop.py
- dsp_repair.py
- BenchMind — Autonomous Multimodal Hardware & Signal Diagnostics Agent
- __init__.py
- benchmind

## God Nodes (most connected - your core abstractions)
1. `run_autonomous_loop()` - 15 edges
2. `generate_stream()` - 7 edges
3. `BiquadDF2T` - 6 edges
4. `parse_uart_naive()` - 6 edges
5. `parse_uart_repaired()` - 6 edges
6. `design_butterworth_hpf()` - 4 edges
7. `design_butterworth_lpf()` - 4 edges
8. `design_notch_50hz()` - 4 edges
9. `test_uart_resynchronization_recovers_all_valid_frames()` - 4 edges
10. `reconstruct_phase_locked_samples()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `test_autonomous_loop_passes_sandbox_gate()` --calls--> `run_autonomous_loop()`  [EXTRACTED]
  tests/test_benchmind.py → benchmind/agent_loop.py
- `test_uart_resynchronization_recovers_all_valid_frames()` --calls--> `generate_stream()`  [EXTRACTED]
  tests/test_benchmind.py → benchmind/telemetry.py
- `test_uart_resynchronization_recovers_all_valid_frames()` --calls--> `parse_uart_naive()`  [EXTRACTED]
  tests/test_benchmind.py → benchmind/dsp_repair.py
- `test_uart_resynchronization_recovers_all_valid_frames()` --calls--> `parse_uart_repaired()`  [EXTRACTED]
  tests/test_benchmind.py → benchmind/dsp_repair.py
- `run_autonomous_loop()` --calls--> `compute_dft_bin_db()`  [EXTRACTED]
  benchmind/agent_loop.py → benchmind/dsp_repair.py

## Import Cycles
- None detected.

## Communities (9 total, 2 thin omitted)

### Community 0 - "run_autonomous_loop"
Cohesion: 0.33
Nodes (6): Maintain 4 kHz sample-clock continuity across single-frame CRC drops using…, reconstruct_phase_locked_samples(), run_autonomous_loop(), main(), Command-line entry point for BenchMind., test_autonomous_loop_passes_sandbox_gate()

### Community 1 - "test_benchmind.py"
Cohesion: 0.47
Nodes (5): parse_uart_naive(), parse_uart_repaired(), Faulty baseline parser: assumes each read chunk starts on a 9-byte frame…, Synthesized buffered state-machine parser: resynchronizes byte-by-byte on AA 55…, test_uart_resynchronization_recovers_all_valid_frames()

### Community 2 - "BiquadDF2T"
Cohesion: 0.40
Nodes (4): BiquadDF2T, design_butterworth_hpf(), design_butterworth_lpf(), Direct Form II Transposed 2nd-order IIR Biquad filter.

### Community 3 - "telemetry.py"
Cohesion: 0.60
Nodes (4): generate_stream(), pack_frame(), Synthetic 4 kHz 12-bit ADC + framed UART telemetry generator and fault injector., TelemetryStream

### Community 4 - "agent_loop.py"
Cohesion: 0.50
Nodes (3): BenchMindReport, Autonomous Multimodal Diagnose -> Synthesize -> Sandbox Verify Loop (Meta Muse…, compute_rms_mav()

### Community 5 - "dsp_repair.py"
Cohesion: 0.50
Nodes (3): compute_dft_bin_db(), design_notch_50hz(), Baseline vs Autonomous Synthesized Biquad DSP + Buffered CRC-32 UART Parser.

### Community 6 - "BenchMind — Autonomous Multimodal Hardware & Signal Diagnostics Agent"
Cohesion: 0.50
Nodes (3): BenchMind — Autonomous Multimodal Hardware & Signal Diagnostics Agent, Overview, Quick Start

## Knowledge Gaps
- **3 isolated node(s):** `benchmind`, `Overview`, `Quick Start`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 15 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_autonomous_loop()` connect `run_autonomous_loop` to `test_benchmind.py`, `BiquadDF2T`, `telemetry.py`, `agent_loop.py`, `dsp_repair.py`?**
  _High betweenness centrality (0.162) - this node is a cross-community bridge._
- **Why does `BiquadDF2T` connect `BiquadDF2T` to `dsp_repair.py`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Why does `parse_uart_naive()` connect `test_benchmind.py` to `run_autonomous_loop`, `agent_loop.py`, `dsp_repair.py`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **What connects `benchmind`, `Overview`, `Quick Start` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._