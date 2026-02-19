
import math

def fingerprint_similarity(features):

    magnitude = sum(abs(v) for v in features.values())
    score = 100 / (1 + math.log1p(magnitude))

    return round(score,2)
