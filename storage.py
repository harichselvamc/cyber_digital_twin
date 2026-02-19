
import os
import json
import joblib

BASE_DIR = "data"


def _user_dir(user):
    path = os.path.join(BASE_DIR, user)
    os.makedirs(path, exist_ok=True)
    return path


def save_samples(user, samples):
    path = os.path.join(_user_dir(user), "samples.json")
    with open(path, "w") as f:
        json.dump(samples, f)


def load_samples(user):
    path = os.path.join(_user_dir(user), "samples.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def save_model(user, model):
    path = os.path.join(_user_dir(user), "model.joblib")
    joblib.dump(model, path)


def load_model(user):
    path = os.path.join(_user_dir(user), "model.joblib")
    if os.path.exists(path):
        return joblib.load(path)
    return None
