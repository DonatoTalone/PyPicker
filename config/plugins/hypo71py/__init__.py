"""
hypo71py: Python implementation of the HYPO71 earthquake location algorithm.

This package provides:
- a FORTRAN-faithful numerical core
- Pythonic domain models (stations, phases, velocity models)
- optional interface layers for external ecosystems (e.g. ObsPy)
"""

from hypo71py.core.single import SINGLE
from hypo71py.model.station_phase import Station, StationPhases, PhasePick
from hypo71py.model.velocity_model import CrustalVelocityModel

__all__ = [
    "SINGLE",
    "Station",
    "StationPhases",
    "PhasePick",
    "CrustalVelocityModel",
]