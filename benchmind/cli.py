"""Command-line entry point for BenchMind v0.2.0."""
from __future__ import annotations
import argparse
import dataclasses
import json
from typing import Optional, Sequence
from .agent_loop import run_autonomous_loop
from .copilot import run_hardware_copilot
from .dashboard import write_dashboard


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="BenchMind v0.2.0 Autonomous Hardware & Signal Diagnostics Agent")
    parser.add_argument("--output", "-o", help="Write JSON verification report to path", default="")
    parser.add_argument("--dashboard", "-d", help="Write interactive HTML bench dashboard to path (e.g. web/index.html)", default="")
    parser.add_argument("--copilot-only", action="store_true", help="Output only the v0.2.0 AI Hardware Copilot diagnosis JSON")
    args = parser.parse_args(argv)

    if args.dashboard:
        write_dashboard(args.dashboard)

    if args.copilot_only:
        copilot_data = run_hardware_copilot()
        out = json.dumps(copilot_data, indent=2, ensure_ascii=False)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out + "\n")
        print(out)
        return 0

    report = run_autonomous_loop()
    data = dataclasses.asdict(report)
    out = json.dumps(data, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out + "\n")
    print(out)
    return 0 if report.sandbox_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
