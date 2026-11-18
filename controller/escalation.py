"""Coder escalation settings: the model ladder, the mode and the per-plan cost cap.

All of it is read from the server environment (.env). Nothing here is chosen by the UI
or the voice user. With CODER_LADDER unset or AUTO_ESCALATE=off the ladder is inactive:
one rung, the normal coder, and nothing new is parsed.
"""
import os
from dataclasses import dataclass

from controller.providers import (
    PlannerConfigurationError,
    PlannerProvider,
    _resolve_role,
)

# Counted for a cloud attempt whose cost Aider did not print (timeout, crash, lost output),
# so unseen spend cannot grow without bound under the cost cap.
UNPARSED_CLOUD_COST = 0.10
DEFAULT_MAX_PLAN_COST = 1.00
_MODES = ("on", "suggest", "off")
_PROVIDERS = ("openai", "ollama", "lmstudio")


@dataclass(frozen=True)
class Rung:
    provider: PlannerProvider
    spec: str   # "provider:model"
    label: str  # last "/" segment of the model id

    def info(self) -> dict:
        return {"label": self.label, "provider": self.provider.name,
                "model": self.provider.model, "location": self.provider.location}


@dataclass(frozen=True)
class Escalation:
    active: bool
    mode: str
    rungs: tuple
    max_plan_cost: float
    local_only: bool

    def info(self) -> dict:
        return {"mode": self.mode, "max_plan_cost": self.max_plan_cost,
                "local_only": self.local_only,
                "rungs": [r.info() for r in self.rungs], "start": 0}


def rung_for_provider(provider: PlannerProvider) -> Rung:
    return Rung(provider, f"{provider.name}:{provider.model}",
                provider.model.rsplit("/", 1)[-1] or provider.model)


def _choice(values, name: str, default: str, allowed) -> str:
    value = values.get(name, "").strip().lower() or default
    if value not in allowed:
        raise PlannerConfigurationError(f"{name} must be one of {', '.join(repr(a) for a in allowed)}")
    return value


def _parse_ladder(raw: str, values) -> list[Rung]:
    rungs: list[Rung] = []
    seen: set[str] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        prefix = f"CODER_LADDER entry '{entry}': "
        if not entry:
            raise PlannerConfigurationError("CODER_LADDER has an empty entry")
        name, sep, model = entry.partition(":")
        name, model = name.strip().lower(), model.strip()
        if not sep or not model:
            raise PlannerConfigurationError(prefix + "expected provider:model")
        if name not in _PROVIDERS:
            raise PlannerConfigurationError(prefix + "provider must be one of 'openai', 'ollama', or 'lmstudio'")
        spec = f"{name}:{model}"
        if spec in seen:
            raise PlannerConfigurationError(prefix + "duplicate entry")
        seen.add(spec)
        try:
            provider = _resolve_role(
                {**values, "_RUNG_PROVIDER": name, "_RUNG_MODEL": model},
                "_RUNG_PROVIDER", "_RUNG_MODEL", "openai")
        except PlannerConfigurationError as exc:
            raise PlannerConfigurationError(prefix + str(exc).replace("_RUNG_PROVIDER", "the provider")
                                            .replace("_RUNG_MODEL", "the model")) from None
        rungs.append(rung_for_provider(provider))
    return rungs


def resolve_escalation(start: PlannerProvider, env=None) -> Escalation:
    """Resolve the ladder for a run whose starting coder is `start`."""
    values = os.environ if env is None else env
    raw = values.get("CODER_LADDER", "").strip()
    only = rung_for_provider(start)
    inactive = Escalation(False, "off", (only,), 0.0, False)
    if not raw:
        return inactive
    mode = _choice(values, "AUTO_ESCALATE", "on", _MODES)
    if mode == "off":
        return inactive
    raw_cap = values.get("MAX_PLAN_COST", "").strip() or str(DEFAULT_MAX_PLAN_COST)
    try:
        cap = float(raw_cap)
    except ValueError:
        cap = 0.0
    if not cap > 0 or cap != cap or cap == float("inf"):
        raise PlannerConfigurationError("MAX_PLAN_COST must be a positive number of dollars")
    local_only = _choice(values, "ESCALATE_LOCAL_ONLY", "off", ("on", "off")) == "on"
    ladder = _parse_ladder(raw, values)
    if local_only:
        if not start.is_local:
            raise PlannerConfigurationError(
                f"ESCALATE_LOCAL_ONLY=on but the selected coder {only.label} runs in the cloud")
        ladder = [r for r in ladder if r.provider.is_local]
    specs = [r.spec for r in ladder]
    if only.spec in specs:
        rungs = ladder[specs.index(only.spec):]
    else:
        rungs = [only, *ladder]
    return Escalation(True, mode, tuple(rungs), cap, local_only)
