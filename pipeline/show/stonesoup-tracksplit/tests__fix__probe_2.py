import json
from datetime import datetime, timedelta

import numpy as np

obs = {}


def rec(key, fn):
    try:
        obs[key] = fn()
    except Exception as e:  # observations only
        obs[key] = "error:" + type(e).__name__


from stonesoup.measures import Euclidean, Mahalanobis  # noqa: E402
from stonesoup.models.measurement.nonlinear import CartesianToBearingRange  # noqa: E402
from stonesoup.types.angle import Bearing  # noqa: E402
from stonesoup.types.array import StateVector  # noqa: E402
from stonesoup.types.detection import Detection  # noqa: E402
from stonesoup.types.hypothesis import SingleHypothesis  # noqa: E402
from stonesoup.types.prediction import GaussianStatePrediction  # noqa: E402
from stonesoup.updater.kalman import ExtendedKalmanUpdater, UnscentedKalmanUpdater  # noqa: E402

t = datetime(2026, 9, 29, 7, 7, 30)
radar = CartesianToBearingRange(
    ndim_state=4, mapping=(0, 2), noise_covar=np.diag([np.radians(0.35) ** 2, 7.5 ** 2]))
# A vessel due west of the radar, just south of the line; the plot lands just north of it.
prediction = GaussianStatePrediction(
    StateVector([-4000.0, 0.3, -6.0, 5.0]), np.diag([30.0 ** 2, 2.0, 30.0 ** 2, 2.0]),
    timestamp=t)
plot = Detection(StateVector([np.pi - 0.002, 4001.0]), timestamp=t, measurement_model=radar)

for name, updater in (("ekf", ExtendedKalmanUpdater(radar)),
                      ("ukf", UnscentedKalmanUpdater(radar))):
    def mahal(updater=updater):
        return round(float(Mahalanobis()(updater.predict_measurement(prediction), plot)), 3)

    def posterior(updater=updater):
        post = updater.update(SingleHypothesis(prediction, plot))
        return [round(float(post.state_vector[0]), 1), round(float(post.state_vector[2]), 1)]

    rec(name + "_mahalanobis", mahal)
    rec(name + "_posterior_xy", posterior)

rec("euclidean", lambda: round(float(Euclidean()(
    ExtendedKalmanUpdater(radar).predict_measurement(prediction), plot)), 4))
typed = StateVector([Bearing(np.pi - 0.01), 1000.0])
plain = StateVector([0.03, 2.0])
rec("typed_plus_plain", lambda: [round(float(v), 4) for v in (typed + plain).ravel()])
rec("plain_minus_typed", lambda: [round(float(v), 4) for v in (plain - typed).ravel()])
rec("typed_minus_plain", lambda: [round(float(v), 4) for v in (typed - plain).ravel()])
rec("scalar_shift", lambda: round(float((typed + np.float64(0.02))[0]), 4))
print()
print(json.dumps(obs, sort_keys=True))
