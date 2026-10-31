"""
Radiation pattern and ray geometry calculations for focal mechanism analysis.
Calculates take-off angles and azimuths via 1D crustal models and theoretical P polarities.
"""

import numpy as np
from obspy.geodetics import gps2dist_azimuth, locations2degrees


def calculate_takeoff_and_azimuth(evla, evlo, evdp_km, stla, stlo, taup_model=None):
    """
    Compute source-to-station azimuth and P-wave take-off angle (incidence angle at source).
    
    Parameters
    ----------
    evla : float
        Hypocenter latitude in degrees.
    evlo : float
        Hypocenter longitude in degrees.
    evdp_km : float
        Focal depth in kilometers.
    stla : float
        Station latitude in degrees.
    stlo : float
        Station longitude in degrees.
    taup_model : obspy.taup.TauPyModel, optional
        Pre-compiled TauP velocity model. If None, loaded via picker_utils_qt.
        
    Returns
    -------
    dist_km : float
        Epicentral distance in km.
    azimuth : float
        Source-to-station azimuth in degrees [0, 360).
    takeoff_angle : float
        Take-off angle at source in degrees from downward vertical (0° = down, 90° = horizontal, 180° = up).
    takeoff_lower : float
        Effective take-off angle mapped to the lower focal hemisphere (<= 90°).
    azimuth_lower : float
        Effective azimuth mapped to the lower focal hemisphere.
    """
    dist_m, az, _ = gps2dist_azimuth(evla, evlo, stla, stlo)
    dist_km = dist_m / 1000.0
    dist_deg = locations2degrees(evla, evlo, stla, stlo)

    # Calculate takeoff angle using TauP model if available
    takeoff = None
    if taup_model is None:
        try:
            import picker_utils_qt as utils
            taup_model = utils.get_or_create_taup_model()
        except Exception:
            pass

    if taup_model is not None and evdp_km >= 0:
        try:
            # Query P arrivals
            arrivals = taup_model.get_travel_times(
                source_depth_in_km=max(0.1, float(evdp_km)),
                distance_in_degree=max(1e-5, float(dist_deg)),
                phase_list=["p", "P", "Pn", "Pg"]
            )
            if arrivals:
                # Take the earliest first arrival
                first_arr = arrivals[0]
                takeoff = float(first_arr.takeoff_angle)
        except Exception:
            takeoff = None

    # Fallback to straight-ray flat-earth approximation if TauP is not available or failed
    if takeoff is None or np.isnan(takeoff):
        # Straight line from hypocenter (depth evdp_km) to surface station (depth 0)
        # angle with downward vertical: theta = arctan2(dist_km, -depth) if upgoing
        # In straight ray from (0,0,-depth) to (dist, 0):
        # dz = -evdp_km (upwards). Take-off angle from downward vertical:
        if evdp_km <= 0.01:
            takeoff = 90.0
        else:
            # Ray travels upwards towards surface: angle from downward vertical is 180 - arctan(dist/depth)
            takeoff = 180.0 - float(np.degrees(np.arctan2(dist_km, evdp_km)))

    # Map upgoing rays (> 90°) to lower hemisphere by projecting through the origin:
    # ray(az, takeoff) is equivalent in double-couple radiation to ray((az + 180)%360, 180 - takeoff)
    if takeoff > 90.0:
        takeoff_lower = 180.0 - takeoff
        azimuth_lower = (az + 180.0) % 360.0
    else:
        takeoff_lower = takeoff
        azimuth_lower = az % 360.0

    return round(dist_km, 2), round(az, 1), round(takeoff, 1), round(takeoff_lower, 1), round(azimuth_lower, 1)


def compute_p_radiation_pattern(strike, dip, rake, azimuths, takeoff_angles):
    """
    Compute theoretical P-wave radiation amplitudes and polarities for given fault orientation.
    Vectorized over arrays of azimuths and takeoff angles.
    
    Parameters
    ----------
    strike : float or array-like
        Fault strike in degrees.
    dip : float or array-like
        Fault dip in degrees.
    rake : float or array-like
        Fault rake in degrees.
    azimuths : array-like
        Source-to-station azimuths in degrees.
    takeoff_angles : array-like
        Take-off angles in degrees from downward vertical (0° = down).
        
    Returns
    -------
    amplitudes : numpy.ndarray
        Theoretical P-wave radiation amplitude factor:
        A_P = (n . r) * (u . r)
    polarities : numpy.ndarray
        +1 for compression (Up / C), -1 for dilatation (Down / D), 0 for nodal.
    """
    azs = np.radians(azimuths)
    ins = np.radians(takeoff_angles)

    # Unit ray vector r: r1 = sin(i)*cos(az), r2 = sin(i)*sin(az), r3 = cos(i)
    r1 = np.sin(ins) * np.cos(azs)
    r2 = np.sin(ins) * np.sin(azs)
    r3 = np.cos(ins)

    phi = np.radians(strike)
    delta = np.radians(dip)
    lam = np.radians(rake)

    # Unit normal vector n
    n1 = -np.sin(delta) * np.sin(phi)
    n2 = np.sin(delta) * np.cos(phi)
    n3 = -np.cos(delta)

    # Unit slip vector u
    u1 = np.cos(lam) * np.cos(phi) + np.cos(delta) * np.sin(lam) * np.sin(phi)
    u2 = np.cos(lam) * np.sin(phi) - np.cos(delta) * np.sin(lam) * np.cos(phi)
    u3 = -np.sin(delta) * np.sin(lam)

    # Dot products
    n_dot_r = n1 * r1 + n2 * r2 + n3 * r3
    u_dot_r = u1 * r1 + u2 * r2 + u3 * r3

    amp = n_dot_r * u_dot_r

    pol = np.zeros_like(amp, dtype=int)
    pol[amp > 1e-7] = 1
    pol[amp < -1e-7] = -1

    return amp, pol
