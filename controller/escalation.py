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
from controller.model_servers import server_names

# Counted for a cloud attempt whose cost Aider did not print AND whose model has no known
# price, so unseen spend cannot grow without bound under the cost cap.
UNPARSED_CLOUD_COST = 0.10

# Dollars per 1M tokens (input, output) for models whose price we know. Used to estimate an
# attempt Aider did not price (timeout, crash, lost output) from the token counts it printed.
MODEL_PRICES = {
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6.1-terra": (1.00, 5.00),
    "gpt-6.1-sol": (2.00, 10.00),
    "gpt-6-sol": (2.00, 10.00),
    "gpt-6.2-sol": (2.00, 10.00),
    "gpt-6.2-astra": (8.00, 40.00),
    "gpt-6-astra": (10.00, 50.00),
}
# Tokens assumed when an attempt printed no counts: the size of a typical task attempt.
ASSUMED_TOKENS = (8_000, 4_000)


def _token_count(text: str) -> float:
    return float(text[:-1]) * 1000 if text.endswith("k") else float(text)


def estimate_cloud_cost(model: str, output: str) -> float:
    """Estimated dollars for one cloud attempt that Aider did not price.

    Uses the "Tokens: X sent, Y received" lines Aider prints, priced at the model's known
    rate. With no token lines it assumes a typical attempt. A model with no known price
    gets the flat UNPARSED_CLOUD_COST.
    """
    import re

    price = MODEL_PRICES.get(model.split("/")[-1].lower())
    if price is None:
        return UNPARSED_CLOUD_COST
    pairs = re.findall(r"Tokens:\s*([\d.]+k?)\s*sent,\s*([\d.]+k?)\s*received", output or "")
    sent, received = (
        (sum(_token_count(s) for s, _ in pairs), sum(_token_count(r) for _, r in pairs))
        if pairs else ASSUMED_TOKENS
    )
    return round(sent / 1e6 * price[0] + received / 1e6 * price[1], 6)
DEFAULT_MAX_PLAN_COST = 1.00
_MODES = ("on", "suggest", "off")
_PROVIDERS = ("openai", "ollama", "lmstudio")


@dataclass(frozen=True)
class Rung:
    provider: PlannerProvider
    spec: str   # "provider:model"
    label: str  # last "/" segment of the model id

    def info(self) -> dict:
        return {"label": self.label, "provider": self.provider.server or self.provider.name,
                "server": self.provider.server,
                "model": self.provider.model, "location": self.provider.location}


@dataclass(frozen=True)
class Escalation:
    active: bool
    mode: str
    rungs: tuple
    max_plan_cost: float
    local_only: bool
    scope: str = "off"  # ESCALATE_LOCAL_ONLY: "off", "machine" (on) or "lan"

    def info(self) -> dict:
        return {"mode": self.mode, "max_plan_cost": self.max_plan_cost,
                "local_only": self.local_only, "scope": self.scope,
                "rungs": [r.info() for r in self.rungs], "start": 0}


def rung_for_provider(provider: PlannerProvider) -> Rung:
    short = provider.model.rsplit("/", 1)[-1] or provider.model
    if provider.server:
        return Rung(provider, f"{provider.server}:{provider.model}", f"{short}@{provider.server}")
    return Rung(provider, f"{provider.name}:{provider.model}", short)


def _choice(values, name: str, default: str, allowed) -> str:
    value = values.get(name, "").strip().lower() or default
    if value not in allowed:
        raise PlannerConfigurationError(f"{name} must be one of {', '.join(repr(a) for a in allowed)}")
    return value


def _parse_ladder(raw: str, values) -> list[Rung]:
    rungs: list[Rung] = []
    seen: set[str] = set()
    servers = server_names(values)
    for entry in raw.split(","):
        entry = entry.strip()
        prefix = f"CODER_LADDER entry '{entry}': "
        if not entry:
            raise PlannerConfigurationError("CODER_LADDER has an empty entry")
        name, sep, model = entry.partition(":")
        name, model = name.strip().lower(), model.strip()
        if not sep or not model:
            raise PlannerConfigurationError(prefix + "expected provider:model")
        if name not in _PROVIDERS and name not in servers:
            raise PlannerConfigurationError(
                prefix + "provider must be one of 'openai', 'ollama', or 'lmstudio'"
                + (" or a configured model server" if servers else ""))
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
    setting = _choice(values, "ESCALATE_LOCAL_ONLY", "off", ("on", "off", "lan"))
    scope = {"off": "off", "on": "machine", "lan": "lan"}[setting]
    local_only = scope != "off"
    ladder = _parse_ladder(raw, values)
    if local_only:
        if start.location == "cloud":
            raise PlannerConfigurationError(
                f"ESCALATE_LOCAL_ONLY=on but the selected coder {only.label} runs in the cloud")
        if scope == "machine":
            if start.location == "lan":
                raise PlannerConfigurationError(
                    f"ESCALATE_LOCAL_ONLY=on but the selected coder {only.label} runs on the local "
                    "network (use ESCALATE_LOCAL_ONLY=lan to allow it)")
            ladder = [r for r in ladder if r.provider.location == "local"]
        else:
            ladder = [r for r in ladder if r.provider.location != "cloud"]
    specs = [r.spec for r in ladder]
    if only.spec in specs:
        rungs = ladder[specs.index(only.spec):]
    else:
        rungs = [only, *ladder]
    return Escalation(True, mode, tuple(rungs), cap, local_only, scope)
