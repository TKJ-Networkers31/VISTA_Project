"""Routing policy for hybrid inference (Phase 4). Pure functions, stdlib only: no I/O, no network, no provider imports.

Rules (ADR-0002 / API_PROVIDER_POLICY.md):
- local_only: never external, whatever the request says.
- hybrid: external only for capabilities listed in `external_capabilities` AND with per-request consent.
- external_fallback: local first; external only after a local failure that is eligible AND with consent.
Invalid input is never retried or forwarded externally. Every decision is explicit and carries a reason code;
nothing falls back silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Optional

MODES = ("local_only", "hybrid", "external_fallback")
EXTERNAL_MODES = ("hybrid", "external_fallback")
# local failures after which an external attempt may be considered (never invalid_input / cancelled)
FALLBACK_ELIGIBLE_CATEGORIES = frozenset({"unavailable", "timeout", "provider_internal", "resource_limit"})


class PolicyError(ValueError):
    """Carries a stable `code` so the API can map it to a structured error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class ExternalConfig:
    enabled: bool = False                      # master switch (VISTA_EXTERNAL_ENABLED / VISTA_NIM_ENABLED)
    has_credentials: bool = False              # True only if a key is configured; the key itself never enters here
    capabilities: FrozenSet[str] = field(default_factory=frozenset)  # verified capabilities of the external provider
    external_capabilities: FrozenSet[str] = field(default_factory=frozenset)  # routed externally in hybrid mode
    local_capabilities: FrozenSet[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class PolicyDecision:
    target: str          # "local" | "external"
    reason: str          # stable code
    allow_fallback: bool = False  # external may be tried after an eligible local failure


def _external_ready(cfg: ExternalConfig, capability: str) -> Optional[PolicyError]:
    if not cfg.enabled:
        return PolicyError("EXTERNAL_DISABLED", "External providers are disabled by configuration.")
    if not cfg.has_credentials:
        return PolicyError("EXTERNAL_NOT_CONFIGURED", "The external provider has no credentials configured.")
    if capability not in cfg.capabilities:
        return PolicyError("CAPABILITY_UNSUPPORTED", f"The external provider does not support '{capability}'.")
    return None


def decide(mode: str, capability: str, consent: bool, cfg: ExternalConfig) -> PolicyDecision:
    """First routing step. Raises PolicyError when the request cannot be served within policy."""
    if mode not in MODES:
        raise PolicyError("INVALID_MODE", f"Unknown mode '{mode}'.")
    local_ok = capability in cfg.local_capabilities
    if mode == "local_only":
        if not local_ok:
            raise PolicyError("CAPABILITY_UNSUPPORTED", f"No local provider supports '{capability}'.")
        return PolicyDecision("local", "LOCAL_ONLY")
    if mode == "hybrid":
        if capability in cfg.external_capabilities:
            if not consent:
                raise PolicyError("CONSENT_REQUIRED", "This capability is routed externally and needs your consent.")
            err = _external_ready(cfg, capability)
            if err:
                raise err
            return PolicyDecision("external", "HYBRID_EXTERNAL")
        if not local_ok:
            raise PolicyError("CAPABILITY_UNSUPPORTED", f"No provider is configured for '{capability}'.")
        return PolicyDecision("local", "HYBRID_LOCAL")
    # external_fallback
    if local_ok:
        ready = consent and _external_ready(cfg, capability) is None
        return PolicyDecision("local", "FALLBACK_LOCAL_FIRST", allow_fallback=ready)
    if not consent:
        raise PolicyError("CONSENT_REQUIRED", "No local provider exists for this capability; external needs consent.")
    err = _external_ready(cfg, capability)
    if err:
        raise err
    return PolicyDecision("external", "FALLBACK_NO_LOCAL")


def may_fallback(decision: PolicyDecision, local_error_category: str, retryable_hint: bool = True) -> bool:
    """After a local failure: may the caller now try the external provider?"""
    return (decision.target == "local" and decision.allow_fallback
            and local_error_category in FALLBACK_ELIGIBLE_CATEGORIES and retryable_hint)
