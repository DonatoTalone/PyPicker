"""
Kinematics and source parameter calculations for focal mechanism analysis.
Conventions follow Aki & Richards (1980 / 2002) and Frohlich (1992).
"""

import numpy as np


def strike_dip_rake_to_vectors(strike, dip, rake):
    """
    Convert strike, dip, rake in degrees to fault normal n and slip direction u.
    
    Coordinate system: x1 = North, x2 = East, x3 = Down (Aki & Richards convention).
    
    Parameters
    ----------
    strike : float
        Fault strike in degrees [0, 360).
    dip : float
        Fault dip in degrees [0, 90].
    rake : float
        Slip angle (rake) in degrees [-180, 180].
        
    Returns
    -------
    n : numpy.ndarray (3,)
        Unit normal vector pointing into the hanging wall.
    u : numpy.ndarray (3,)
        Unit slip vector in direction of hanging wall motion.
    """
    phi = np.radians(strike)
    delta = np.radians(dip)
    lam = np.radians(rake)

    # Unit normal to fault plane (hanging wall side)
    n = np.array([
        -np.sin(delta) * np.sin(phi),
        np.sin(delta) * np.cos(phi),
        -np.cos(delta)
    ], dtype=float)

    # Unit slip vector
    u = np.array([
        np.cos(lam) * np.cos(phi) + np.cos(delta) * np.sin(lam) * np.sin(phi),
        np.cos(lam) * np.sin(phi) - np.cos(delta) * np.sin(lam) * np.cos(phi),
        -np.sin(delta) * np.sin(lam)
    ], dtype=float)

    return n, u


def vectors_to_strike_dip_rake(n, u):
    """
    Convert fault normal n and slip vector u back to (strike, dip, rake) in degrees.
    Ensures dip is in [0, 90] and strike in [0, 360).
    """
    # If normal vector points downward (n[2] > 0), invert both vectors so dip <= 90
    if n[2] > 0:
        n = -n
        u = -u

    # Ensure dip in [0, 90]
    cos_delta = -n[2]
    cos_delta = np.clip(cos_delta, -1.0, 1.0)
    delta_rad = np.arccos(cos_delta)
    sin_delta = np.sin(delta_rad)

    if sin_delta < 1e-7:
        # Horizontal fault plane (dip = 0)
        strike_deg = 0.0
        rake_deg = np.degrees(np.arctan2(u[1], u[0]))
        dip_deg = 0.0
    else:
        # strike from normal vector: n = (-sin(delta)*sin(phi), sin(delta)*cos(phi), -cos(delta))
        phi_rad = np.arctan2(-n[0], n[1])
        strike_deg = float(np.degrees(phi_rad) % 360.0)

        # rake from slip vector: u[2] = -sin(delta)*sin(lambda)
        sin_lam = -u[2] / sin_delta
        sin_lam = np.clip(sin_lam, -1.0, 1.0)
        cos_lam = u[0] * np.cos(phi_rad) + u[1] * np.sin(phi_rad)
        lam_rad = np.arctan2(sin_lam, cos_lam)
        rake_deg = float(np.degrees(lam_rad))

    dip_deg = float(np.degrees(delta_rad))
    return round(strike_deg, 1), round(dip_deg, 1), round(rake_deg, 1)


def fault_plane_to_auxiliary(strike, dip, rake):
    """
    Compute auxiliary nodal plane 2 (strike2, dip2, rake2) from plane 1 (strike, dip, rake).
    By symmetry of double-couple source: n2 = u1, u2 = n1.
    """
    n, u = strike_dip_rake_to_vectors(strike, dip, rake)
    return vectors_to_strike_dip_rake(u, n)


def vector_to_trend_plunge(vec):
    """
    Convert a 3D unit vector [North, East, Down] to Trend (azimuth in [0, 360))
    and Plunge (dip below horizontal in [0, 90]).
    """
    # If pointing upward (Down < 0), invert so plunge is positive below horizon
    v = np.array(vec, dtype=float)
    if v[2] < 0:
        v = -v

    norm = np.linalg.norm(v)
    if norm > 0:
        v = v / norm

    # Plunge: angle with horizontal plane
    plunge_rad = np.arcsin(np.clip(v[2], 0.0, 1.0))
    plunge_deg = float(np.degrees(plunge_rad))

    # Trend: azimuth in North-East plane
    trend_rad = np.arctan2(v[1], v[0])
    trend_deg = float(np.degrees(trend_rad) % 360.0)

    return round(trend_deg, 1), round(plunge_deg, 1)


def fault_plane_to_pt(strike, dip, rake):
    """
    Compute P (Pressure) and T (Tension) and B (Null) axis trend and plunge.
    
    P = (n - u) / sqrt(2)  (Compression quadrant axis)
    T = (n + u) / sqrt(2)  (Dilatation quadrant axis)
    B = n x u
    
    Returns
    -------
    p_axis : tuple (trend, plunge)
    t_axis : tuple (trend, plunge)
    b_axis : tuple (trend, plunge)
    """
    n, u = strike_dip_rake_to_vectors(strike, dip, rake)
    
    p_vec = (n - u) / np.sqrt(2.0)
    t_vec = (n + u) / np.sqrt(2.0)
    b_vec = np.cross(n, u)

    p_axis = vector_to_trend_plunge(p_vec)
    t_axis = vector_to_trend_plunge(t_vec)
    b_axis = vector_to_trend_plunge(b_vec)

    return p_axis, t_axis, b_axis


def classify_faulting(strike, dip, rake, p_plunge=None, t_plunge=None, b_plunge=None):
    """
    Classify earthquake faulting regime using Frohlich (1992) / Zoback (1992) plunge criteria.
    
    Categories:
    - Normal (NF)
    - Strike-Slip (SS)
    - Thrust / Reverse (TF)
    - Normal-Strike-Slip / Oblique Normal (NS)
    - Thrust-Strike-Slip / Oblique Thrust (TS)
    - Unknown / Odd
    """
    if p_plunge is None or t_plunge is None or b_plunge is None:
        p_ax, t_ax, b_ax = fault_plane_to_pt(strike, dip, rake)
        p_plunge = p_ax[1]
        t_plunge = t_ax[1]
        b_plunge = b_ax[1]

    # Frohlich (1992) ternary plunges:
    # Plunges are between 0 and 90 degrees
    # Normal: P plunge >= 52° or (P > 40° and T < 40°)
    # Thrust: T plunge >= 52° or (T > 40° and P < 40°)
    # Strike-slip: B plunge >= 52° or (B > 45° and P < 40° and T < 40°)
    if p_plunge >= 52.0:
        return "Normal Faulting (NF)"
    elif t_plunge >= 52.0:
        return "Thrust / Reverse (TF)"
    elif b_plunge >= 52.0:
        return "Strike-Slip (SS)"
    elif p_plunge > 40.0 and b_plunge < 40.0:
        return "Oblique Normal (NS)"
    elif t_plunge > 40.0 and b_plunge < 40.0:
        return "Oblique Thrust (TS)"
    elif b_plunge > 40.0:
        return "Strike-Slip with Oblique Component"
    else:
        # Fallback to rake criteria
        abs_rake = abs(rake)
        if 60.0 <= rake <= 120.0:
            return "Thrust / Reverse (TF)"
        elif -120.0 <= rake <= -60.0:
            return "Normal Faulting (NF)"
        elif abs_rake <= 30.0 or abs_rake >= 150.0:
            return "Strike-Slip (SS)"
        elif -150.0 < rake < -120.0 or -60.0 < rake < -30.0:
            return "Oblique Normal (NS)"
        else:
            return "Oblique Thrust (TS)"


def calculate_azimuthal_gap(azimuths):
    """
    Calculate maximum azimuthal gap in degrees between recording stations.
    
    Parameters
    ----------
    azimuths : list or numpy.ndarray
        List of station azimuths in degrees [0, 360).
        
    Returns
    -------
    float
        Largest angular separation between adjacent stations.
    """
    if len(azimuths) < 2:
        return 360.0

    azs = np.sort(np.asarray(azimuths, dtype=float) % 360.0)
    diffs = np.diff(azs)
    wrap_diff = (360.0 - azs[-1]) + azs[0]
    all_diffs = np.append(diffs, wrap_diff)
    return float(round(np.max(all_diffs), 1))
