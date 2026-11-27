from functools import partial

import numpy as np
from sklearn.feature_selection import SelectKBest, VarianceThreshold, mutual_info_classif
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from core.errors import DomainError

from .features import FEATURE_NAMES
from .reference_pack import LABELS


def vectors(rows):
    return np.array([[row[name] for name in FEATURE_NAMES] for row in rows], dtype=float)


def model_pipeline(count=5):
    return Pipeline([
        ("variance", VarianceThreshold(threshold=0.0)),
        ("information", SelectKBest(partial(mutual_info_classif, random_state=19), k=count)),
        ("scale", StandardScaler()),
        ("linear", LogisticRegression(max_iter=600)),
    ])


def chosen_features(model):
    varied = np.array(FEATURE_NAMES)[model.named_steps["variance"].get_support()]
    selector = model.named_steps["information"]
    return {
        str(feature): round(float(score), 5)
        for feature, score, chosen in zip(varied, selector.scores_, selector.get_support())
        if chosen
    }


def classify(features, specimens, signature):
    columns, labels, scan_group = zip(*specimens)
    x, y, groups = vectors(columns), np.array(labels), np.array(scan_group)
    if len(set(groups)) < 4 or len(set(y)) != len(LABELS):
        raise DomainError(409, "need independent scan groups for each fault label")
    split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=29)
    training, holdout = next(split.split(x, y, groups))
    if any(set(y[index]) != set(LABELS) for index in (training, holdout)):
        raise DomainError(409, "training and holdout must each represent all fault labels")

    varied_columns = int((np.var(x[training], axis=0) > 0).sum())
    if varied_columns < 2:
        raise DomainError(409, "reference scans have too few varying signals")
    selection_count = min(5, varied_columns)
    validation = model_pipeline(selection_count).fit(x[training], y[training])
    guesses = validation.predict(x[holdout])
    model = model_pipeline(selection_count).fit(x, y)
    label = str(model.predict(vectors([features]))[0])
    probabilities = model.predict_proba(vectors([features]))[0]
    return label, {
        "selected_mutual_information": chosen_features(model),
        "removed_constants": [
            name for name, kept in zip(FEATURE_NAMES, model.named_steps["variance"].get_support()) if not kept
        ],
        "holdout_specimens": len(holdout),
        "holdout_balanced_accuracy": round(float(balanced_accuracy_score(y[holdout], guesses)), 5),
        "label_order": list(LABELS),
        "holdout_confusion": confusion_matrix(y[holdout], guesses, labels=LABELS).tolist(),
        "probabilities": {str(key): round(float(value), 6) for key, value in zip(model.classes_, probabilities)},
        "reference_sha256": signature,
    }
