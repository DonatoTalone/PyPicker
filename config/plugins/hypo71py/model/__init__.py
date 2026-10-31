"""
Domain models for hypo71py.

These classes describe stations, phase picks, and velocity models,
and provide Pythonic structure around the numerical core.
"""

from hypo71py.model.station_phase import Station, StationPhases, PhasePick
from hypo71py.model.velocity_model import CrustalVelocityModel

__all__ = [
    "Station",
    "StationPhases",
    "PhasePick",
    "CrustalVelocityModel",
]