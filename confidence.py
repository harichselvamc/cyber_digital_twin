def confidence_score(anomaly_score):
    """
    Convert anomaly score into confidence %.
    Higher normality → higher confidence.
    """
    score = 50 + anomaly_score * 200
    score = max(0, min(100, score))
    return round(score,2)
