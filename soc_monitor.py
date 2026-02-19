
_live_users = {}

def update_user(user, risk):
    _live_users[user] = {
        "risk_score": risk["risk_score"],
        "level": risk["level"],
        "action": risk["action"],
        "time": risk["ts"]
    }

def get_live_users():
    return _live_users
