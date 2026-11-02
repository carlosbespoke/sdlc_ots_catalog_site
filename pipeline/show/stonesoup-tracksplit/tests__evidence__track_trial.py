"""Harbour radar trial: run the plot tracker over a recorded plot file and summarise the tracks.

    python track_trial.py plots_2026-09-29.csv
"""
import sys
from collections import Counter

import numpy as np

from stonesoup.dataassociator.neighbour import GNNWith2DAssignment
from stonesoup.deleter.time import UpdateTimeStepsDeleter
from stonesoup.hypothesiser.distance import DistanceHypothesiser
from stonesoup.initiator.simple import MultiMeasurementInitiator
from stonesoup.measures import Mahalanobis
from stonesoup.models.measurement.nonlinear import CartesianToBearingRange
from stonesoup.models.transition.linear import (
    CombinedLinearGaussianTransitionModel, ConstantVelocity)
from stonesoup.predictor.kalman import ExtendedKalmanPredictor
from stonesoup.reader.generic import CSVDetectionReader
from stonesoup.tracker.simple import MultiTargetTracker
from stonesoup.types.state import GaussianState
from stonesoup.updater.kalman import ExtendedKalmanUpdater

radar = CartesianToBearingRange(
    ndim_state=4, mapping=(0, 2),
    noise_covar=np.diag([np.radians(0.35) ** 2, 7.5 ** 2]))
plots = CSVDetectionReader(
    sys.argv[1], state_vector_fields=("bearing_rad", "range_m"), time_field="time")

transition = CombinedLinearGaussianTransitionModel([ConstantVelocity(0.05)] * 2)
predictor = ExtendedKalmanPredictor(transition)
updater = ExtendedKalmanUpdater(radar)
hypothesiser = DistanceHypothesiser(predictor, updater, Mahalanobis(), missed_distance=4)
initiator = MultiMeasurementInitiator(
    GaussianState([[0], [0], [0], [0]], np.diag([0, 8 ** 2, 0, 8 ** 2])),
    measurement_model=radar,
    deleter=UpdateTimeStepsDeleter(time_steps_since_update=2),
    updater=updater,
    data_associator=GNNWith2DAssignment(hypothesiser),
    min_points=3)
tracker = MultiTargetTracker(
    initiator=initiator, deleter=UpdateTimeStepsDeleter(time_steps_since_update=3),
    detector=plots, data_associator=GNNWith2DAssignment(hypothesiser), updater=updater)

tracks = set()
for time, current in tracker:
    tracks |= current

long_tracks = sorted((t for t in tracks if len(t) >= 20), key=lambda t: t[0].timestamp)
print(f"{len(tracks)} tracks, {len(long_tracks)} with >= 20 scans")
for n, track in enumerate(long_tracks, 1):
    first, last = track[0], track[-1]
    print(f"  T{n:02d} {first.timestamp:%H:%M:%S}-{last.timestamp:%H:%M:%S} {len(track):4d} scans"
          f"  start ({first.state_vector[0]:8.0f},{first.state_vector[2]:8.0f})"
          f"  end ({last.state_vector[0]:8.0f},{last.state_vector[2]:8.0f})")
