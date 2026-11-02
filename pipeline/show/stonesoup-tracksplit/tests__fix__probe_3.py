import json
from datetime import datetime, timedelta

import numpy as np

obs = {}
try:
    from stonesoup.deleter.time import UpdateTimeStepsDeleter
    from stonesoup.types.detection import Detection
    from stonesoup.types.hypothesis import SingleHypothesis
    from stonesoup.types.prediction import GaussianStatePrediction
    from stonesoup.types.track import Track
    from stonesoup.types.update import GaussianStateUpdate

    t0 = datetime(2026, 9, 29, 7, 0)

    def track_with_misses(misses, updates=3):
        states = []
        for k in range(updates + misses):
            t = t0 + timedelta(seconds=2 * k)
            pred = GaussianStatePrediction(np.array([[float(k)]]), np.eye(1), timestamp=t)
            if k < updates:
                det = Detection(np.array([[float(k)]]), timestamp=t)
                states.append(GaussianStateUpdate(np.array([[float(k)]]), np.eye(1),
                                                  SingleHypothesis(pred, det), timestamp=t))
            else:
                states.append(pred)
        return Track(states)

    obs["grid"] = {str(n): [bool(UpdateTimeStepsDeleter(time_steps_since_update=n)
                                 .check_for_deletion(track_with_misses(m)))
                            for m in range(6)]
                   for n in (1, 2, 3, 4)}
    # Two states sharing a timestamp (a second sensor's prediction at the same time).
    track = track_with_misses(2)
    track.append(GaussianStatePrediction(np.array([[9.0]]), np.eye(1), timestamp=track[-1].timestamp))
    obs["shared_time"] = [bool(UpdateTimeStepsDeleter(time_steps_since_update=n)
                               .check_for_deletion(track)) for n in (2, 3)]
    # delete_tracks on a mixed set: which of the tracks (by misses) would go.
    tracks = {m: track_with_misses(m) for m in range(5)}
    gone = UpdateTimeStepsDeleter(time_steps_since_update=3).delete_tracks(set(tracks.values()))
    obs["deleted_misses"] = sorted(m for m, t in tracks.items() if t in gone)
except Exception as e:  # observations only
    obs["error"] = type(e).__name__
print()
print(json.dumps(obs, sort_keys=True))
