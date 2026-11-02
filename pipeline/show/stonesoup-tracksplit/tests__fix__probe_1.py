import json
from datetime import datetime, timedelta, timezone

import numpy as np

obs = {}
try:
    from stonesoup.dataassociator.neighbour import GNNWith2DAssignment
    from stonesoup.deleter.time import UpdateTimeStepsDeleter
    from stonesoup.hypothesiser.distance import DistanceHypothesiser
    from stonesoup.initiator.simple import MultiMeasurementInitiator
    from stonesoup.measures import Mahalanobis
    from stonesoup.models.measurement.nonlinear import CartesianToBearingRange
    from stonesoup.models.transition.linear import (
        CombinedLinearGaussianTransitionModel, ConstantVelocity)
    from stonesoup.predictor.kalman import ExtendedKalmanPredictor
    from stonesoup.tracker.simple import MultiTargetTracker
    from stonesoup.types.detection import Detection
    from stonesoup.types.state import GaussianState
    from stonesoup.updater.kalman import ExtendedKalmanUpdater

    # Recorded-style plots: bearing/range as plain floats, as a file reader delivers them.
    rng = np.random.default_rng(24)
    t0 = datetime(2026, 9, 29, 7, 0, tzinfo=timezone.utc)
    vessels = [(-3100.0, 0.3, 2600.0, -5.8, 0, 520), (-5400.0, 0.4, -2300.0, 5.1, 40, 600),
               (2600.0, -4.2, 3100.0, -1.1, 0, 450), (900.0, 0.9, -4200.0, 3.2, 100, 600),
               (-1500.0, 3.5, 4200.0, -0.4, 200, 600)]
    scans = {}
    for k in range(600):
        t = t0 + timedelta(seconds=2.0 * k + rng.normal(0, 0.05))
        stamp = datetime.fromisoformat(t.strftime("%Y-%m-%dT%H:%M:%S.%f"))
        plots = scans.setdefault(stamp, [])
        for (x, vx, y, vy, k0, k1) in vessels:
            if not (k0 <= k <= k1) or rng.random() > 0.995:
                continue
            px, py = x + vx * 2.0 * (k - k0), y + vy * 2.0 * (k - k0)
            b = np.arctan2(py, px) + rng.normal(0, np.radians(0.35))
            b = (b + np.pi) % (2 * np.pi) - np.pi
            plots.append((round(b, 6), round(np.hypot(px, py) + rng.normal(0, 7.5), 1)))
        for _ in range(rng.poisson(0.6)):
            plots.append((round(rng.uniform(-np.pi, np.pi), 6), round(rng.uniform(300, 7000), 1)))

    radar = CartesianToBearingRange(
        ndim_state=4, mapping=(0, 2), noise_covar=np.diag([np.radians(0.35) ** 2, 7.5 ** 2]))
    feed = [(stamp, {Detection(np.array([[b], [r]], dtype=float), timestamp=stamp)
                     for b, r in plots}) for stamp, plots in sorted(scans.items())]
    transition = CombinedLinearGaussianTransitionModel([ConstantVelocity(0.05)] * 2)
    predictor = ExtendedKalmanPredictor(transition)
    updater = ExtendedKalmanUpdater(radar)
    hypothesiser = DistanceHypothesiser(predictor, updater, Mahalanobis(), missed_distance=4)
    initiator = MultiMeasurementInitiator(
        GaussianState([[0], [0], [0], [0]], np.diag([0, 8 ** 2, 0, 8 ** 2])),
        measurement_model=radar, deleter=UpdateTimeStepsDeleter(time_steps_since_update=2),
        updater=updater, data_associator=GNNWith2DAssignment(hypothesiser), min_points=3)

    class Feed:
        def __iter__(self):
            return iter(feed)

    tracker = MultiTargetTracker(
        initiator=initiator, deleter=UpdateTimeStepsDeleter(time_steps_since_update=3),
        detector=Feed(), data_associator=GNNWith2DAssignment(hypothesiser), updater=updater)
    tracks = set()
    for _, current in tracker:
        tracks |= current
    t_ref = feed[0][0]
    long_tracks = sorted((t for t in tracks if len(t) >= 20), key=lambda t: (t[0].timestamp, len(t)))
    obs["long_tracks"] = len(long_tracks)
    obs["spans"] = [[round((t[0].timestamp - t_ref).total_seconds()),
                     round((t[-1].timestamp - t_ref).total_seconds()), len(t)]
                    for t in long_tracks]
except Exception as e:  # observations only
    obs["error"] = type(e).__name__
print()
print(json.dumps(obs, sort_keys=True))
