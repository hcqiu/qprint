"""Verification policy is independent of compiler and dependency versions."""
from .paths import WorkspaceError


def safe_policy(value="inherit"):
    if type(value) is bool:
        return "require" if value else "off"
    if value not in ("inherit", "require", "off"):
        raise WorkspaceError("Agda safe policy must be inherit, require or off (legacy booleans are accepted)")
    return value


def policy_summary(context):
    if context.language != "agda":
        return {"axiom_audit": False}
    return {"safe": safe_policy(context.safe), "mode": context.mode, "source_options": "preserved"}


def check_outcomes(checks, context):
    """Never infer native type-check success from a failed safe audit."""
    status = checks[-1].status if checks else "not_run"
    required = context.language == "agda" and safe_policy(context.safe) == "require"
    return {"typecheck": status if not required or status == "passed" else "unknown",
            "safe_audit": status if required else "not_run"}
