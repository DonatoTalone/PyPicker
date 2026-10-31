"""
FOCMEC Grid-Search Solver in pure Python/NumPy.
Systematic grid search over double-couple focal sphere for acceptable solutions.
"""

import numpy as np
from .kinematics import (
    fault_plane_to_auxiliary,
    fault_plane_to_pt,
    classify_faulting,
    calculate_azimuthal_gap,
    strike_dip_rake_to_vectors,
    vectors_to_strike_dip_rake,
)
from .radiation import compute_p_radiation_pattern


def generate_grid_vectors(grid_step=5.0):
    """
    Generate unit normal n and slip vectors u for all grid points (strike, dip, rake).
    
    Parameters
    ----------
    grid_step : float
        Angular sampling step in degrees (default: 5.0).
        
    Returns
    -------
    strikes : numpy.ndarray (M,)
    dips : numpy.ndarray (M,)
    rakes : numpy.ndarray (M,)
    n_matrix : numpy.ndarray (M, 3)
    u_matrix : numpy.ndarray (M, 3)
    """
    strike_vals = np.arange(0.0, 360.0, grid_step, dtype=float)
    dip_vals = np.arange(grid_step, 90.0 + 1e-4, grid_step, dtype=float)
    rake_vals = np.arange(-180.0, 180.0, grid_step, dtype=float)

    # Meshgrid across all 3 orientation angles
    s_grid, d_grid, r_grid = np.meshgrid(strike_vals, dip_vals, rake_vals, indexing="ij")
    s_flat = s_grid.ravel()
    d_flat = d_grid.ravel()
    r_flat = r_grid.ravel()

    phi = np.radians(s_flat)
    delta = np.radians(d_flat)
    lam = np.radians(r_flat)

    sin_delta = np.sin(delta)
    cos_delta = np.cos(delta)
    sin_phi = np.sin(phi)
    cos_phi = np.cos(phi)
    sin_lam = np.sin(lam)
    cos_lam = np.cos(lam)

    # Normal vector n: [-sin(delta)*sin(phi), sin(delta)*cos(phi), -cos(delta)]
    n_mat = np.column_stack([
        -sin_delta * sin_phi,
        sin_delta * cos_phi,
        -cos_delta
    ])

    # Slip vector u:
    # [cos(lam)*cos(phi) + cos(delta)*sin(lam)*sin(phi),
    #  cos(lam)*sin(phi) - cos(delta)*sin(lam)*cos(phi),
    #  -sin(delta)*sin(lam)]
    u_mat = np.column_stack([
        cos_lam * cos_phi + cos_delta * sin_lam * sin_phi,
        cos_lam * sin_phi - cos_delta * sin_lam * cos_phi,
        -sin_delta * sin_lam
    ])

    return s_flat, d_flat, r_flat, n_mat, u_mat


# Cached grid for standard step sizes to avoid recomputing trigonometric tables
_GRID_CACHE = {}


def get_cached_grid(grid_step=5.0):
    """Retrieve or compute cached orientation vectors for a given grid step."""
    step_key = round(float(grid_step), 2)
    if step_key not in _GRID_CACHE:
        _GRID_CACHE[step_key] = generate_grid_vectors(grid_step=step_key)
    return _GRID_CACHE[step_key]


def solve_focal_mechanism(
    stations,
    azimuths,
    takeoff_angles,
    polarities,
    max_errors=1,
    grid_step=5.0,
):
    """
    Execute systematic FOCMEC grid search over focal sphere for double-couple solutions.
    
    Parameters
    ----------
    stations : list of str
        Station names.
    azimuths : list or numpy.ndarray
        Source-to-station azimuths in degrees.
    takeoff_angles : list or numpy.ndarray
        Take-off angles in degrees from downward vertical.
    polarities : list or numpy.ndarray
        Observed first-motion polarities: +1 for Up/Compression, -1 for Down/Dilatation.
    max_errors : int
        Maximum number of polarity misfits allowed (default: 1).
    grid_step : float
        Grid search angular resolution in degrees (default: 5.0).
        
    Returns
    -------
    dict
        Comprehensive solution dictionary containing:
        - 'best_solution': dict (strike, dip, rake, plane 2, P/T axes, regime)
        - 'acceptable_solutions': list of dicts
        - 'num_acceptable': int
        - 'min_errors': int
        - 'max_errors_allowed': int
        - 'azimuthal_gap': float
        - 'num_polarities': int
        - 'station_evaluations': list of dicts with per-station fit
    """
    num_pols = len(polarities)
    if num_pols < 4:
        raise ValueError(
            f"At least 4 station polarities are required for focal mechanism determination (provided: {num_pols})."
        )

    az_arr = np.asarray(azimuths, dtype=float)
    to_arr = np.asarray(takeoff_angles, dtype=float)
    pol_obs = np.asarray(polarities, dtype=int)

    # Station ray unit vectors r: r1 = sin(i)*cos(az), r2 = sin(i)*sin(az), r3 = cos(i)
    ins_rad = np.radians(to_arr)
    azs_rad = np.radians(az_arr)
    r_mat = np.column_stack([
        np.sin(ins_rad) * np.cos(azs_rad),
        np.sin(ins_rad) * np.sin(azs_rad),
        np.cos(ins_rad)
    ])  # Shape: (N, 3)

    # Retrieve cached orientation grid
    s_all, d_all, r_all, n_all, u_all = get_cached_grid(grid_step=grid_step)
    # n_all: (M, 3), u_all: (M, 3)

    # Radiation amplitude factor A = (n . r) * (u . r)
    # (M, 3) @ (3, N) -> (M, N)
    n_dot_r = n_all @ r_mat.T
    u_dot_r = u_all @ r_mat.T
    amp = n_dot_r * u_dot_r  # Shape: (M, N)

    # Theoretical polarity: +1 if amp > 0, -1 if amp < 0
    # Misfit count: where theoretical polarity has opposite sign to observation
    # amp * pol_obs < 0 is true when signs differ!
    misfit_mask = (amp * pol_obs[np.newaxis, :]) < -1e-8
    misfit_counts = np.sum(misfit_mask, axis=1)

    min_misfit = int(np.min(misfit_counts))
    effective_max_err = max(max_errors, min_misfit)

    # Acceptable indices
    valid_idxs = np.where(misfit_counts <= effective_max_err)[0]
    num_acceptable = len(valid_idxs)

    if num_acceptable == 0:
        # Fallback to absolute minimum misfit solutions
        valid_idxs = np.where(misfit_counts == min_misfit)[0]
        num_acceptable = len(valid_idxs)

    # Collect acceptable solutions
    acceptable_list = []
    for idx in valid_idxs:
        s1 = float(s_all[idx])
        d1 = float(d_all[idx])
        rk1 = float(r_all[idx])
        s2, d2, rk2 = fault_plane_to_auxiliary(s1, d1, rk1)
        p_ax, t_ax, b_ax = fault_plane_to_pt(s1, d1, rk1)
        regime = classify_faulting(s1, d1, rk1, p_ax[1], t_ax[1], b_ax[1])
        errs = int(misfit_counts[idx])

        acceptable_list.append({
            "strike": s1,
            "dip": d1,
            "rake": rk1,
            "strike2": s2,
            "dip2": d2,
            "rake2": rk2,
            "p_axis": p_ax,
            "t_axis": t_ax,
            "b_axis": b_ax,
            "regime": regime,
            "misfit": errs,
        })

    # Find the representative best solution (centroid of minimum misfit cluster)
    min_err_idxs = [idx for idx in valid_idxs if misfit_counts[idx] == min_misfit]
    if len(min_err_idxs) == 1:
        best_idx = min_err_idxs[0]
    else:
        # Medoid approach: select the solution closest to the mean vectors
        sub_n = n_all[min_err_idxs]
        sub_u = u_all[min_err_idxs]
        mean_n = np.mean(sub_n, axis=0)
        mean_u = np.mean(sub_u, axis=0)
        if np.linalg.norm(mean_n) > 0:
            mean_n /= np.linalg.norm(mean_n)
        if np.linalg.norm(mean_u) > 0:
            mean_u /= np.linalg.norm(mean_u)

        dist_to_mean = (
            np.linalg.norm(sub_n - mean_n, axis=1) +
            np.linalg.norm(sub_u - mean_u, axis=1)
        )
        best_idx = min_err_idxs[int(np.argmin(dist_to_mean))]

    best_s = float(s_all[best_idx])
    best_d = float(d_all[best_idx])
    best_r = float(r_all[best_idx])
    best_s2, best_d2, best_r2 = fault_plane_to_auxiliary(best_s, best_d, best_r)
    best_p, best_t, best_b = fault_plane_to_pt(best_s, best_d, best_r)
    best_regime = classify_faulting(best_s, best_d, best_r, best_p[1], best_t[1], best_b[1])

    best_solution = {
        "strike": best_s,
        "dip": best_d,
        "rake": best_r,
        "strike2": best_s2,
        "dip2": best_d2,
        "rake2": best_r2,
        "p_axis": best_p,
        "t_axis": best_t,
        "b_axis": best_b,
        "regime": best_regime,
        "misfit": int(misfit_counts[best_idx]),
    }

    # Evaluate per-station fit with best solution
    _, theo_pols = compute_p_radiation_pattern(best_s, best_d, best_r, az_arr, to_arr)
    station_evals = []
    for i, sta in enumerate(stations):
        obs = int(pol_obs[i])
        calc = int(theo_pols[i])
        is_misfit = (obs != 0 and calc != 0 and obs != calc)
        station_evals.append({
            "station": sta,
            "azimuth": float(az_arr[i]),
            "takeoff": float(to_arr[i]),
            "observed": obs,
            "calculated": calc,
            "is_misfit": bool(is_misfit),
        })

    gap = calculate_azimuthal_gap(az_arr)

    return {
        "best_solution": best_solution,
        "acceptable_solutions": acceptable_list,
        "num_acceptable": num_acceptable,
        "min_misfit": min_misfit,
        "max_errors_allowed": int(max_errors),
        "azimuthal_gap": gap,
        "num_polarities": num_pols,
        "station_evaluations": station_evals,
        "grid_step": float(grid_step),
    }
