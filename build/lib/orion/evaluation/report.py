"""Report formatter."""

from __future__ import annotations

from .ablation import EvaluationReport


def format_text_report(report: EvaluationReport) -> str:
    lines: list[str] = []
    lines.append(f"ORION EVALUATION REPORT — reference: {report.reference}")
    lines.append(f"folds: {report.n_folds}")
    lines.append("")
    lines.append(
        f"{'spec':<20} {'mae':>8} {'rmse':>8} {'bias':>8} {'dir_acc':>8} {'sig_t':>8}"
    )
    for name, s in report.summaries.items():
        sig = report.significance_vs_reference.get(name)
        p = f"{sig.p_value_t:.3f}" if sig else "-"
        lines.append(
            f"{name:<20} {s.mae:>8.4f} {s.rmse:>8.4f} {s.bias:>8.4f} "
            f"{s.directional_accuracy:>8.3f} {p:>8}"
        )
    return "\n".join(lines)
