
import risk_logger

def build_replay_sequence():

    history = risk_logger.load_history()

    replay = []

    for h in history:
        replay.append({
            "time": h["ts"],
            "risk": h["risk_score"],
            "level": h["level"],
            "action": h["action"]
        })

    return replay
