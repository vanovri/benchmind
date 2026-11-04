"""BenchMind: Autonomous Multimodal Hardware & Signal Diagnostics Agent."""
__version__ = "0.2.0"

from .triage import (
    MuseSparkOpenTriageAdapter,
    BasetenMuseSparkClient,
    TriageAdapter,
    validate_triage_response,
    validate_evidence_ids,
    validate_finding_ids,
    validate_hardware_evaluated,
    deterministic_offline_triage,
    call_baseten_muse_spark,
    BASETEN_API_URL,
    BASETEN_MODEL_ID,
    ALLOWED_EVIDENCE_IDS,
    ALLOWED_FINDING_IDS,
)
from .dsp_repair import BiquadDF2T, validate_biquad_stability, check_biquad_impulse_stability
from .agent_loop import BenchMindReport, run_autonomous_loop
from .copilot import (
    HACKATHON_TEAM_ID,
    HardwareCopilot,
    CopilotDiagnosis,
    RootCauseHypothesis,
    ProbeActionItem,
    analyze_uart_telemetry,
    analyze_dsp_spectrum,
    run_hardware_copilot,
    validate_copilot_diagnosis,
)
from .dashboard import (
    build_dashboard_dataset,
    generate_dashboard_html,
    write_dashboard,
)

__all__ = [
    "__version__",
    "HACKATHON_TEAM_ID",
    "MuseSparkOpenTriageAdapter",
    "BasetenMuseSparkClient",
    "TriageAdapter",
    "validate_triage_response",
    "validate_evidence_ids",
    "validate_finding_ids",
    "BiquadDF2T",
    "BenchMindReport",
    "run_autonomous_loop",
    "HardwareCopilot",
    "CopilotDiagnosis",
    "RootCauseHypothesis",
    "ProbeActionItem",
    "analyze_uart_telemetry",
    "analyze_dsp_spectrum",
    "run_hardware_copilot",
    "validate_copilot_diagnosis",
    "build_dashboard_dataset",
    "generate_dashboard_html",
    "write_dashboard",
]
