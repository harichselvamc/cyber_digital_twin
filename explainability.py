FEATURES = [
    "key_rate",
    "iki_mean",
    "iki_std",
    "hold_mean",
    "hold_std",
    "mouse_speed_mean",
    "mouse_speed_std",
    "click_rate",
]


def explain(features):
    """
    Simple deviation scoring.
    Higher value = more suspicious feature.
    """
    importance = {}

    for k in FEATURES:
        importance[k] = abs(features.get(k, 0))

    # normalize
    total = sum(importance.values()) + 1e-6

    for k in importance:
        importance[k] /= total

    return importance
