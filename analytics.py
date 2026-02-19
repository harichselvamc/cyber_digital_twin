import storage
from model import DigitalTwinModel


def evaluate_far_frr(user: str | None = None):
    """
    FAR/FRR evaluation.
    - If user is provided: evaluates using that user's enrolled samples.
    - If user is None: uses "admin" by default.
    """

    if not user:
        user = "admin"

    samples = storage.load_samples(user)
    if not samples:
        return {"error": f"No enrollment data for user: {user}"}

    model = DigitalTwinModel()
    model.train(samples)

    genuine_total = 0
    false_reject = 0

    
    for s in samples:
        res = model.evaluate(s)
        genuine_total += 1
        if res.action != "ALLOW":
            false_reject += 1

    FRR = false_reject / genuine_total if genuine_total else 0

    imposter_total = 0
    false_accept = 0

    
    for s in samples:
        fake = {k: float(v) * 2.5 for k, v in s.items()}  
        res = model.evaluate(fake)

        imposter_total += 1
        if res.action == "ALLOW":
            false_accept += 1

    FAR = false_accept / imposter_total if imposter_total else 0

    return {
        "user": user,
        "FAR": round(FAR, 4),
        "FRR": round(FRR, 4),
        "genuine_tests": genuine_total,
        "imposter_tests": imposter_total,
    }
