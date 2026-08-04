"""Leakage-safe, interpretable ML baselines over generated integrity scenarios."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Callable, Iterable

import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from app.evaluation.kinematic_harness import (
    SCENARIO_CLASSES,
    DatasetSplit,
    KinematicScenario,
    ScenarioClass,
    ScenarioType,
)
from app.services.kinematics import EvaluationStatus, evaluate_pair
from app.services.windowed_kinematics import WindowPolicy, evaluate_window


FEATURE_SCHEMA_VERSION = "1.0"
MODEL_SUITE_VERSION = "1.0-development"
MINIMUM_PREFIX_OBSERVATIONS = 2


class FeatureStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    ABSTAIN = "ABSTAIN"


FEATURE_NAMES = (
    "observation_count",
    "duration_seconds",
    "mean_interval_seconds",
    "interval_std_seconds",
    "mean_receive_latency_seconds",
    "maximum_receive_latency_seconds",
    "unique_icao_count",
    "unique_provenance_count",
    "pair_flag_count",
    "pair_insufficient_count",
    "maximum_implied_speed_knots",
    "maximum_reported_acceleration_knots_per_second",
    "maximum_turn_rate_degrees_per_second",
    "maximum_derived_vertical_rate_fpm",
    "maximum_speed_disagreement_knots",
    "window_flag_count",
    "window_insufficient_count",
    "maximum_window_position_residual_nm",
)

CIRCULAR_FEATURES = (
    "pair_flag_count",
    "window_flag_count",
    "maximum_implied_speed_knots",
    "maximum_reported_acceleration_knots_per_second",
    "maximum_turn_rate_degrees_per_second",
    "maximum_derived_vertical_rate_fpm",
    "maximum_speed_disagreement_knots",
    "maximum_window_position_residual_nm",
)


@dataclass(frozen=True)
class ScenarioFeatures:
    scenario_id: str
    source_session_id: str
    split: DatasetSplit
    scenario_type: ScenarioType
    scenario_class: ScenarioClass
    prefix_end_index: int
    status: FeatureStatus
    abstain_reason: str | None
    values: tuple[float, ...]

    def as_mapping(self) -> dict[str, float]:
        return dict(zip(FEATURE_NAMES, self.values))


@dataclass(frozen=True)
class ScenarioPrediction:
    scenario_id: str
    scenario_type: ScenarioType
    scenario_class: ScenarioClass
    alerted: bool
    detected: bool
    abstained: bool
    pre_scenario_alert: bool
    time_to_detect_seconds: float | None


def _maximum(values: Iterable[float]) -> float:
    materialized = tuple(values)
    return max(materialized, default=0.0)


def extract_features(scenario: KinematicScenario) -> ScenarioFeatures:
    """Extract one documented feature vector without assigning malicious intent."""
    observations = scenario.observations
    prefix_end_index = len(observations) - 1
    if len(observations) < MINIMUM_PREFIX_OBSERVATIONS:
        return ScenarioFeatures(
            scenario_id=scenario.scenario_id,
            source_session_id=scenario.source_session_id,
            split=scenario.split,
            scenario_type=scenario.scenario_type,
            scenario_class=SCENARIO_CLASSES[scenario.scenario_type],
            prefix_end_index=prefix_end_index,
            status=FeatureStatus.ABSTAIN,
            abstain_reason="At least two observations are required.",
            values=tuple(0.0 for _ in FEATURE_NAMES),
        )

    intervals = [
        (current.observed_at - previous.observed_at).total_seconds()
        for previous, current in zip(observations, observations[1:])
    ]
    duration_seconds = (observations[-1].observed_at - observations[0].observed_at).total_seconds()
    pair_evaluations = [
        evaluate_pair(previous, current)
        for previous, current in zip(observations, observations[1:])
    ]
    scored_pairs = [
        evaluation
        for evaluation in pair_evaluations
        if evaluation.status is not EvaluationStatus.INSUFFICIENT_DATA
    ]
    if duration_seconds <= 0 or not scored_pairs:
        reason = (
            "Observation duration must be positive."
            if duration_seconds <= 0
            else "No consecutive pair has enough evidence for feature extraction."
        )
        return ScenarioFeatures(
            scenario_id=scenario.scenario_id,
            source_session_id=scenario.source_session_id,
            split=scenario.split,
            scenario_type=scenario.scenario_type,
            scenario_class=SCENARIO_CLASSES[scenario.scenario_type],
            prefix_end_index=prefix_end_index,
            status=FeatureStatus.ABSTAIN,
            abstain_reason=reason,
            values=tuple(0.0 for _ in FEATURE_NAMES),
        )

    window_policy = WindowPolicy()
    window_evaluations = [
        evaluate_window(observations[: end_index + 1], policy=window_policy)
        for end_index in range(
            window_policy.minimum_observations - 1,
            len(observations),
        )
    ]
    measurements = [evaluation.measurements for evaluation in pair_evaluations]
    window_measurements = [evaluation.measurements for evaluation in window_evaluations]
    receive_latencies = [
        max((item.received_at - item.observed_at).total_seconds(), 0.0)
        for item in observations
    ]
    values = (
        float(len(observations)),
        duration_seconds,
        statistics.mean(intervals),
        statistics.pstdev(intervals),
        statistics.mean(receive_latencies),
        max(receive_latencies),
        float(len({item.icao_hex for item in observations})),
        float(
            len(
                {
                    item.provenance.model_dump_json()
                    for item in observations
                }
            )
        ),
        float(
            sum(
                evaluation.status is EvaluationStatus.FLAGGED
                for evaluation in pair_evaluations
            )
        ),
        float(
            sum(
                evaluation.status is EvaluationStatus.INSUFFICIENT_DATA
                for evaluation in pair_evaluations
            )
        ),
        _maximum(item.get("implied_ground_speed_knots", 0.0) for item in measurements),
        _maximum(
            item.get("reported_acceleration_knots_per_second", 0.0)
            for item in measurements
        ),
        _maximum(item.get("turn_rate_degrees_per_second", 0.0) for item in measurements),
        _maximum(item.get("derived_vertical_rate_fpm", 0.0) for item in measurements),
        _maximum(item.get("speed_disagreement_knots", 0.0) for item in measurements),
        float(
            sum(
                evaluation.status is EvaluationStatus.FLAGGED
                for evaluation in window_evaluations
            )
        ),
        float(
            sum(
                evaluation.status is EvaluationStatus.INSUFFICIENT_DATA
                for evaluation in window_evaluations
            )
        ),
        _maximum(item.get("position_residual_nm", 0.0) for item in window_measurements),
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"non-finite feature generated for {scenario.scenario_id}")
    return ScenarioFeatures(
        scenario_id=scenario.scenario_id,
        source_session_id=scenario.source_session_id,
        split=scenario.split,
        scenario_type=scenario.scenario_type,
        scenario_class=SCENARIO_CLASSES[scenario.scenario_type],
        prefix_end_index=prefix_end_index,
        status=FeatureStatus.AVAILABLE,
        abstain_reason=None,
        values=values,
    )


def _prefixes(scenario: KinematicScenario) -> Iterable[KinematicScenario]:
    for end_index in range(MINIMUM_PREFIX_OBSERVATIONS - 1, len(scenario.observations)):
        yield replace(
            scenario,
            observations=scenario.observations[: end_index + 1],
        )


def _prefix_label(scenario: KinematicScenario, prefix_end_index: int) -> int:
    if SCENARIO_CLASSES[scenario.scenario_type] is not ScenarioClass.ATTACK:
        return 0
    if scenario.detection_window is None:
        raise ValueError(f"attack scenario {scenario.scenario_id} has no detection window")
    return int(prefix_end_index >= scenario.detection_window.start_index)


def build_training_rows(
    scenarios: Iterable[KinematicScenario],
    *,
    split: DatasetSplit,
) -> tuple[tuple[ScenarioFeatures, ...], np.ndarray]:
    rows = []
    labels = []
    for scenario in scenarios:
        if scenario.split is not split:
            continue
        for prefix in _prefixes(scenario):
            features = extract_features(prefix)
            if features.status is FeatureStatus.ABSTAIN:
                continue
            rows.append(features)
            labels.append(_prefix_label(scenario, features.prefix_end_index))
    return tuple(rows), np.asarray(labels, dtype=int)


def _feature_matrix(rows: Iterable[ScenarioFeatures]) -> np.ndarray:
    return np.asarray([row.values for row in rows], dtype=float)


def train_models(
    scenarios: Iterable[KinematicScenario],
    *,
    seed: int = 20260720,
) -> dict[str, object]:
    rows, labels = build_training_rows(scenarios, split=DatasetSplit.TRAIN)
    if not rows or len(set(labels)) < 2:
        raise ValueError("training data must contain available positive and negative rows")
    matrix = _feature_matrix(rows)
    models: dict[str, object] = {
        "logistic_regression": Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1_000,
                        random_state=seed,
                        solver="liblinear",
                    ),
                ),
            ]
        ),
        "decision_tree": DecisionTreeClassifier(
            max_depth=5,
            min_samples_leaf=5,
            random_state=seed,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=100,
            max_depth=6,
            min_samples_leaf=3,
            n_jobs=1,
            random_state=seed,
        ),
    }
    for model in models.values():
        model.fit(matrix, labels)
    return models


def _rules_predict(features: ScenarioFeatures) -> bool:
    values = features.as_mapping()
    return values["pair_flag_count"] > 0 or values["window_flag_count"] > 0


def _model_predict(model: object, features: ScenarioFeatures) -> bool:
    prediction = model.predict(np.asarray([features.values], dtype=float))
    return bool(prediction[0])


def evaluate_detector(
    scenarios: Iterable[KinematicScenario],
    *,
    name: str,
    predict: Callable[[ScenarioFeatures], bool],
    split: DatasetSplit = DatasetSplit.TEST,
) -> dict[str, object]:
    selected = [scenario for scenario in scenarios if scenario.split is split]
    predictions = []
    for scenario in selected:
        first_alert_index = None
        first_detection_index = None
        available_prefixes = 0
        attack_start = (
            scenario.detection_window.start_index
            if scenario.detection_window is not None
            else None
        )
        for prefix in _prefixes(scenario):
            features = extract_features(prefix)
            if features.status is FeatureStatus.ABSTAIN:
                continue
            available_prefixes += 1
            if predict(features):
                if first_alert_index is None:
                    first_alert_index = features.prefix_end_index
                if attack_start is None:
                    break
                if features.prefix_end_index >= attack_start:
                    first_detection_index = features.prefix_end_index
                    break
        scenario_class = SCENARIO_CLASSES[scenario.scenario_type]
        pre_scenario_alert = (
            first_alert_index is not None
            and attack_start is not None
            and first_alert_index < attack_start
        )
        detected = first_detection_index is not None
        time_to_detect = None
        if detected and attack_start is not None:
            attack_time = scenario.observations[attack_start].observed_at
            detection_time = scenario.observations[first_detection_index].observed_at
            time_to_detect = (detection_time - attack_time).total_seconds()
        predictions.append(
            ScenarioPrediction(
                scenario_id=scenario.scenario_id,
                scenario_type=scenario.scenario_type,
                scenario_class=scenario_class,
                alerted=first_alert_index is not None,
                detected=detected,
                abstained=available_prefixes == 0,
                pre_scenario_alert=pre_scenario_alert,
                time_to_detect_seconds=time_to_detect,
            )
        )

    truth = np.asarray(
        [prediction.scenario_class is ScenarioClass.ATTACK for prediction in predictions],
        dtype=int,
    )
    predicted = np.asarray(
        [
            prediction.detected
            if prediction.scenario_class is ScenarioClass.ATTACK
            else prediction.alerted
            for prediction in predictions
        ],
        dtype=int,
    )
    precision, recall, f1, _ = precision_recall_fscore_support(
        truth,
        predicted,
        average="binary",
        zero_division=0,
    )
    by_type = {}
    for scenario_type in ScenarioType:
        type_predictions = [
            prediction
            for prediction in predictions
            if prediction.scenario_type is scenario_type
        ]
        if not type_predictions:
            continue
        delays = [
            prediction.time_to_detect_seconds
            for prediction in type_predictions
            if prediction.time_to_detect_seconds is not None
        ]
        by_type[scenario_type.value] = {
            "scenarios": len(type_predictions),
            "alerted": sum(item.alerted for item in type_predictions),
            "alert_rate": round(
                sum(item.alerted for item in type_predictions) / len(type_predictions),
                4,
            ),
            "detected": sum(item.detected for item in type_predictions),
            "detection_rate": round(
                sum(item.detected for item in type_predictions) / len(type_predictions),
                4,
            ),
            "abstained": sum(item.abstained for item in type_predictions),
            "pre_scenario_alerts": sum(
                item.pre_scenario_alert for item in type_predictions
            ),
            "median_time_to_detect_seconds": (
                statistics.median(delays) if delays else None
            ),
        }
    controls = [
        item for item in predictions if item.scenario_class is ScenarioClass.CONTROL
    ]
    impairments = [
        item for item in predictions if item.scenario_class is ScenarioClass.IMPAIRMENT
    ]
    return {
        "name": name,
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "scenario_count": len(predictions),
        "abstained_scenarios": sum(item.abstained for item in predictions),
        "pre_scenario_alerts": sum(item.pre_scenario_alert for item in predictions),
        "synthetic_control_sequence_alert_rate": round(
            sum(item.alerted for item in controls) / len(controls),
            4,
        ),
        "synthetic_impairment_sequence_alert_rate": round(
            sum(item.alerted for item in impairments) / len(impairments),
            4,
        ),
        "field_false_alerts_per_flight_hour": None,
        "metrics_by_scenario_type": by_type,
        "predictions": [asdict(prediction) for prediction in predictions],
    }


def _explain_model(name: str, model: object) -> list[dict[str, float | str]]:
    if name == "logistic_regression":
        values = model.named_steps["classifier"].coef_[0]
    else:
        values = model.feature_importances_
    ranked = sorted(
        zip(FEATURE_NAMES, values),
        key=lambda item: abs(float(item[1])),
        reverse=True,
    )
    return [
        {"feature": feature, "importance": round(float(value), 6)}
        for feature, value in ranked[:8]
    ]


def build_ml_report(
    scenarios: Iterable[KinematicScenario],
    *,
    seed: int = 20260720,
    implementation_revision: str,
) -> dict[str, object]:
    """Train on session-isolated prefixes and score only held-out sessions."""
    scenario_tuple = tuple(scenarios)
    models = train_models(scenario_tuple, seed=seed)
    reports_by_split = {}
    for split in (DatasetSplit.VALIDATION, DatasetSplit.TEST):
        reports = {
            "always_normal": evaluate_detector(
                scenario_tuple,
                name="always_normal",
                predict=lambda _: False,
                split=split,
            ),
            "rules_only": evaluate_detector(
                scenario_tuple,
                name="rules_only",
                predict=_rules_predict,
                split=split,
            ),
        }
        for name, model in models.items():
            reports[name] = evaluate_detector(
                scenario_tuple,
                name=name,
                predict=lambda features, selected=model: _model_predict(
                    selected,
                    features,
                ),
                split=split,
            )
        reports_by_split[split.value] = reports
    explanations = {
        name: _explain_model(name, model) for name, model in models.items()
    }
    return {
        "report_schema_version": "1.0",
        "scope": "generated_scenarios_only",
        "suite_version": MODEL_SUITE_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "generator_versions": sorted(
            {scenario.generator_version for scenario in scenario_tuple}
        ),
        "implementation_revision": implementation_revision,
        "sklearn_version": sklearn.__version__,
        "root_seed": seed,
        "feature_names": list(FEATURE_NAMES),
        "circular_feature_warning": list(CIRCULAR_FEATURES),
        "training_source_sessions": len(
            {
                scenario.source_session_id
                for scenario in scenario_tuple
                if scenario.split is DatasetSplit.TRAIN
            }
        ),
        "test_source_sessions": len(
            {
                scenario.source_session_id
                for scenario in scenario_tuple
                if scenario.split is DatasetSplit.TEST
            }
        ),
        "model_configurations": {
            "logistic_regression": {
                "solver": "liblinear",
                "max_iter": 1_000,
                "threshold": 0.5,
            },
            "decision_tree": {
                "max_depth": 5,
                "min_samples_leaf": 5,
            },
            "random_forest": {
                "estimators": 100,
                "max_depth": 6,
                "min_samples_leaf": 3,
            },
        },
        "validation_models": reports_by_split[DatasetSplit.VALIDATION.value],
        "models": reports_by_split[DatasetSplit.TEST.value],
        "explanations": explanations,
        "promotion_decision": "OFFLINE_EVALUATION_ONLY",
        "limitations": [
            "Training and evaluation use generated scenarios, not labeled malicious RF.",
            "Synthetic control alert rates are not field false-positive rates.",
            "Kinematic outputs overlap the generator mechanisms and may be circular features.",
            "A plausible ghost track is intentionally indistinguishable from clean motion without corroboration.",
            "No model is integrated into operator alerts at this checkpoint.",
        ],
    }
