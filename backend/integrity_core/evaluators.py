"""Stable shared facade for parser- and database-independent evaluators."""

from app.services.kinematics import (
    EvaluationStatus,
    KinematicEvaluation,
    KinematicPolicy,
    KinematicRule,
    RuleResult,
    evaluate_pair,
)
from app.services.windowed_kinematics import (
    WindowEvaluation,
    WindowPolicy,
    WindowRule,
    WindowRuleResult,
    evaluate_window,
)

__all__ = [
    "EvaluationStatus",
    "KinematicEvaluation",
    "KinematicPolicy",
    "KinematicRule",
    "RuleResult",
    "WindowEvaluation",
    "WindowPolicy",
    "WindowRule",
    "WindowRuleResult",
    "evaluate_pair",
    "evaluate_window",
]
