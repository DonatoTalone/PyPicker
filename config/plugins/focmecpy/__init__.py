"""
focmecpy: Pure-Python earthquake focal mechanism determination and beachball visualization.
Implements FOCMEC grid search, radiation patterns, kinematic axes, and stereonet plotting.
"""

from .kinematics import (
    fault_plane_to_auxiliary,
    fault_plane_to_pt,
    classify_faulting,
    calculate_azimuthal_gap,
    strike_dip_rake_to_vectors,
    vectors_to_strike_dip_rake,
)
from .radiation import (
    calculate_takeoff_and_azimuth,
    compute_p_radiation_pattern,
)
from .solver import (
    solve_focal_mechanism,
    get_cached_grid,
)
from .io_focmec import (
    write_focmec_inp,
    read_focmec_inp,
    export_focal_mechanism_to_csv,
)
from .plotting import (
    plot_beachball,
    save_beachball_figure,
    to_stereonet_coords,
    get_nodal_plane_points,
)

__all__ = [
    "solve_focal_mechanism",
    "calculate_takeoff_and_azimuth",
    "compute_p_radiation_pattern",
    "fault_plane_to_auxiliary",
    "fault_plane_to_pt",
    "classify_faulting",
    "calculate_azimuthal_gap",
    "strike_dip_rake_to_vectors",
    "vectors_to_strike_dip_rake",
    "write_focmec_inp",
    "read_focmec_inp",
    "export_focal_mechanism_to_csv",
    "plot_beachball",
    "save_beachball_figure",
    "to_stereonet_coords",
    "get_nodal_plane_points",
]
