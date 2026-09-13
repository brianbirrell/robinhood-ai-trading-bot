"""Optional agent identity verification for auto-trading mode.

Adds a verification gate before order execution so only authenticated
agents can place trades. Disabled by default — opt in via config.

The verifier interface is pluggable. The built-in TokenVerifier checks
a runtime token against a trusted secret from env/config. Implement
AgentVerifier for any identity system (JWT, API keys, ZKP, etc.).

How it works:
1. On startup, AGENT_IDENTITY_SECRET is loaded from config (env var).
2. Before each trade, the bot calls check_agent_identity() with a
   runtime token (from the agent's execution context).
3. The verifier checks the runtime token against the trusted secret.
4. If they don't match (or verification fails), the trade is blocked.

This prevents unauthorized processes from executing trades even if
they have access to the Robinhood API credentials.
"""

import logging
import os
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_AUDIT_ENTRIES = 1000


@dataclass
class VerificationResult:
    """Result of an agent identity check."""
    verified: bool
    agent_id: str = ""
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentVerifier(ABC):
    """Pluggable agent identity verifier.

    Implement for any identity system: JWT validation,
    API key lookup, ZKP proof checking, etc.
    """

    @abstractmethod
    def verify(self, runtime_token: str) -> VerificationResult:
        """Verify a runtime token and return the result."""


class TokenVerifier(AgentVerifier):
    """Token-based verifier.

    Compares a runtime token (from the agent's execution context)
    against a trusted secret (from env/config). These must be
    different sources — if the runtime token comes from the same
    config as the secret, verification is meaningless.
    """

    def __init__(self, trusted_secret: str):
        if not trusted_secret:
            raise ValueError(
                "TokenVerifier requires a non-empty trusted secret. "
                "Set AGENT_IDENTITY_SECRET in your environment."
            )
        self._secret = trusted_secret

    def verify(self, runtime_token: str) -> VerificationResult:
        if not runtime_token:
            return VerificationResult(verified=False, reason="no runtime token provided")
        if runtime_token != self._secret:
            return VerificationResult(verified=False, reason="token does not match trusted secret")
        return VerificationResult(verified=True, agent_id="auto-trader")


# Bounded audit log
_audit_log: deque = deque(maxlen=_MAX_AUDIT_ENTRIES)


def check_agent_identity(config, runtime_token: Optional[str] = None) -> Optional[str]:
    """Check agent identity before order execution.

    Args:
        config: The config module with identity settings.
        runtime_token: Token from the agent's execution context.
            If None, reads from AGENT_IDENTITY_RUNTIME_TOKEN env var.

    Returns:
        None if authorized (or verification disabled),
        error message string if denied.
    """
    enabled = getattr(config, "AGENT_IDENTITY_VERIFICATION", False)
    if not enabled:
        return None

    # Trusted secret from config/env (set at deploy time)
    secret = getattr(config, "AGENT_IDENTITY_SECRET", "") or os.environ.get("AGENT_IDENTITY_SECRET", "")
    if not secret:
        msg = "AGENT_IDENTITY_VERIFICATION is enabled but AGENT_IDENTITY_SECRET is not set"
        logger.error(f"[identity] {msg}")
        return msg

    # Runtime token from the execution context (different source)
    token = runtime_token or os.environ.get("AGENT_IDENTITY_RUNTIME_TOKEN", "")
    if not token:
        msg = "No runtime token provided and AGENT_IDENTITY_RUNTIME_TOKEN env var is empty"
        logger.error(f"[identity] {msg}")
        return msg

    verifier = TokenVerifier(secret)
    result = verifier.verify(token)

    _audit_log.append({
        "action": "allow" if result.verified else "deny",
        "agent_id": result.agent_id,
        "reason": result.reason,
        "timestamp": result.timestamp,
    })

    if not result.verified:
        logger.warning(f"[identity] DENIED: {result.reason}")
        return f"Agent identity verification failed: {result.reason}"

    logger.info(f"[identity] Verified: {result.agent_id}")
    return None


def get_audit_log() -> list:
    """Read-only copy of the verification audit log."""
    return list(_audit_log)
