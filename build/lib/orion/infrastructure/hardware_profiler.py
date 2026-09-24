r"""ORION hardware profiler + local model router (Architectural Audit §11/§12).

The :class:`HardwareProfiler` extends the existing
:func:`orion.infrastructure.hardware.detect_hardware` snapshot with:

* CPU count, free disk, OS load (1/5/15-min averages where available)
* GPU name + VRAM (via ``nvidia-smi`` if present)
* Ollama availability probe (HTTP ``/api/version``)
* A :class:`HardwareProfile` that the rest of ORION can pass around
  without re-probing.

The :class:`LocalModelRouter` selects a model tier based on:

* hardware capability
* task complexity (cheap, standard, deep)
* context size requested
* latency budget requested
* available ollama models (if any)

The router never hard-codes "the ORION brain": it returns a
:class:`ModelTier` whose fields name the model, why it was chosen,
and a budget estimate, so the operator can override at any time.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Mapping

from .hardware import HardwareProfile, detect_hardware


@dataclass(frozen=True, slots=True)
class ExtendedHardwareProfile:
    """A richer hardware snapshot the router can decide on."""

    base: HardwareProfile
    cpu_count: int = 0
    free_disk_gb: float = 0.0
    total_disk_gb: float = 0.0
    load1: float | None = None
    load5: float | None = None
    load15: float | None = None
    ollama_available: bool = False
    ollama_models: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "ram_gb": self.base.ram_gb,
            "gpu_name": self.base.gpu_name,
            "cuda_available": self.base.cuda_available,
            "cpu_count": self.cpu_count,
            "free_disk_gb": round(self.free_disk_gb, 2),
            "total_disk_gb": round(self.total_disk_gb, 2),
            "load1": self.load1,
            "load5": self.load5,
            "load15": self.load15,
            "ollama_available": self.ollama_available,
            "ollama_models": list(self.ollama_models),
        }


def _cpu_count() -> int:
    return os.cpu_count() or 0


def _disk_bytes() -> tuple[float, float]:
    try:
        total, used, free = shutil.disk_usage(os.getcwd())
        return free / (1024 ** 3), total / (1024 ** 3)
    except (OSError, AttributeError):
        return 0.0, 0.0


def _loadavg() -> tuple[float | None, float | None, float | None]:
    try:
        one, five, fifteen = os.getloadavg()
        return float(one), float(five), float(fifteen)
    except (OSError, AttributeError):
        return None, None, None


def _nvidia_vram() -> int:
    """Return GPU VRAM in MiB if nvidia-smi is present."""
    if not shutil.which("nvidia-smi"):
        return 0
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return 0
    if result.returncode != 0 or not result.stdout.strip():
        return 0
    try:
        return int(result.stdout.splitlines()[0].strip())
    except (ValueError, IndexError):
        return 0


def _ollama_probe(base_url: str = "http://127.0.0.1:11434", timeout: float = 1.0) -> tuple[bool, tuple[str, ...]]:
    """Probe Ollama: returns (available, models). Never raises."""
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return False, ()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False, ()
    models = tuple(sorted({str(m.get("name", "")) for m in payload.get("models", []) if m.get("name")}))
    return True, models


class HardwareProfiler:
    """Snapshot the host hardware + local inference availability."""

    def __init__(self, *, ollama_url: str = "http://127.0.0.1:11434", probe_ollama: bool = True) -> None:
        self.ollama_url = ollama_url
        self._probe_ollama = probe_ollama

    def snapshot(self) -> ExtendedHardwareProfile:
        base = detect_hardware()
        vram = _nvidia_vram()
        if vram and base.gpu_name is None:
            base = HardwareProfile(ram_gb=base.ram_gb, gpu_name="NVIDIA", cuda_available=True)
        if self._probe_ollama:
            ollama_ok, ollama_models = _ollama_probe(self.ollama_url)
        else:
            ollama_ok, ollama_models = False, ()
        free_gb, total_gb = _disk_bytes()
        load1, load5, load15 = _loadavg()
        return ExtendedHardwareProfile(
            base=base,
            cpu_count=_cpu_count(),
            free_disk_gb=free_gb,
            total_disk_gb=total_gb,
            load1=load1,
            load5=load5,
            load15=load15,
            ollama_available=ollama_ok,
            ollama_models=ollama_models,
        )


# ----------------------------------------------------------------- tiers

TASK_COMPLEXITY = ("cheap", "standard", "deep")


@dataclass(frozen=True, slots=True)
class ModelTier:
    """A router decision: model, backend, and a justification."""

    name: str
    backend: str          # "ollama" | "http" | "noop"
    model: str
    context_window: int
    reason: str
    estimated_latency_s: float
    fallback_to: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "backend": self.backend,
            "model": self.model,
            "context_window": self.context_window,
            "reason": self.reason,
            "estimated_latency_s": round(self.estimated_latency_s, 2),
            "fallback_to": self.fallback_to,
        }


# Default model names ORION will prefer per tier when ollama is up.
DEFAULT_TIERS: dict[str, dict[str, Any]] = {
    "cheap": {
        "name": "qwen2.5:0.5b",
        "context_window": 4_096,
        "estimated_latency_s": 0.4,
        "fallback": "phi3:mini",
    },
    "standard": {
        "name": "qwen2.5:7b",
        "context_window": 32_768,
        "estimated_latency_s": 2.0,
        "fallback": "llama3.1:8b",
    },
    "deep": {
        "name": "qwen2.5:14b",
        "context_window": 32_768,
        "estimated_latency_s": 6.0,
        "fallback": "llama3.1:70b",
    },
}


class LocalModelRouter:
    """Choose a model tier from hardware + task shape (audit §11)."""

    def __init__(
        self,
        profile: ExtendedHardwareProfile | None = None,
        *,
        tiers: Mapping[str, Mapping[str, Any]] | None = None,
        required_disk_gb: float = 5.0,
    ) -> None:
        self.profile = profile or HardwareProfiler().snapshot()
        self.tiers = dict(tiers) if tiers else {k: dict(v) for k, v in DEFAULT_TIERS.items()}
        self.required_disk_gb = required_disk_gb

    # ------------------------------------------------------------- public

    def select(
        self,
        complexity: str = "standard",
        *,
        context_tokens: int = 0,
        latency_budget_s: float | None = None,
    ) -> ModelTier:
        """Pick the best available tier for the task."""
        if complexity not in TASK_COMPLEXITY:
            raise ValueError(f"complexity must be one of {TASK_COMPLEXITY}, got {complexity!r}")
        tier_spec = self.tiers[complexity]
        ram = self.profile.base.ram_gb
        reason_bits: list[str] = []
        if self.profile.ollama_available and self.profile.free_disk_gb < self.required_disk_gb:
            reason_bits.append(f"ollama available but only {self.profile.free_disk_gb:.1f} GB free (need {self.required_disk_gb:.0f})")
        if not self.profile.ollama_available:
            return self._no_ollama_fallback(complexity, reason_bits)
        # Escalate / downgrade based on hardware and constraints.
        chosen = dict(tier_spec)
        model = chosen["name"]
        if ram and ram < 8 and complexity == "deep":
            chosen = dict(self.tiers["standard"])
            model = chosen["name"]
            reason_bits.append(f"RAM {ram}GB < 8; downgraded deep -> standard")
        if context_tokens and context_tokens > chosen["context_window"]:
            chosen = dict(self.tiers["deep"])
            model = chosen["name"]
            reason_bits.append(f"context {context_tokens} > {tier_spec['context_window']}; escalated to deep")
        if latency_budget_s is not None and chosen["estimated_latency_s"] > latency_budget_s:
            chosen = dict(self.tiers["cheap"])
            model = chosen["name"]
            reason_bits.append(f"latency budget {latency_budget_s}s below standard {tier_spec['estimated_latency_s']}s; cheapest")
        if model not in self.profile.ollama_models:
            replacement = next(
                (m for m in self.profile.ollama_models if m == chosen.get("fallback")),
                None,
            )
            if replacement is not None:
                model = replacement
                reason_bits.append(f"requested model not pulled; using {replacement}")
            else:
                reason_bits.append(f"requested model {model!r} not present locally; operator must `ollama pull`")
        return ModelTier(
            name=chosen.get("name", model),
            backend="ollama",
            model=model,
            context_window=int(chosen.get("context_window", 32_768)),
            reason="; ".join(reason_bits) or "hardware + task fit",
            estimated_latency_s=float(chosen.get("estimated_latency_s", 2.0)),
            fallback_to=chosen.get("fallback"),
        )

    # ------------------------------------------------------------- helpers

    def _no_ollama_fallback(self, complexity: str, reason_bits: list[str]) -> ModelTier:
        reason_bits.append("ollama not reachable; routing to cloud HTTP only")
        return ModelTier(
            name="http",
            backend="http",
            model="unset",
            context_window=0,
            reason="; ".join(reason_bits),
            estimated_latency_s=0.0,
            fallback_to=None,
        )

    def select_with_cheapest(self) -> ModelTier:
        return self.select("cheap")

    def summary(self) -> dict[str, Any]:
        return {
            "hardware": self.profile.as_dict(),
            "tiers": {key: dict(value) for key, value in self.tiers.items()},
        }