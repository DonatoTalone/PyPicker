"""
Beachball and focal sphere stereographic projection plotting.
Renders lower-hemisphere equal-area projections with nodal planes, solution ensembles,
P/T axes, and station first-motion polarities.
"""

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, PathPatch
from matplotlib.path import Path as MplPath
from .kinematics import strike_dip_rake_to_vectors


def to_stereonet_coords(azimuth, takeoff_lower):
    """
    Convert station azimuth (deg) and lower-hemisphere takeoff angle (deg <= 90)
    to normalized 2D Cartesian coordinates (x, y) on an equal-area (Schmidt) net.
    Radius = 1.0 at takeoff = 90° (horizontal).
    """
    # Schmidt net: r = sqrt(2) * sin(i / 2)
    # At i = 90°, r = sqrt(2) * sin(45°) = sqrt(2) * (1/sqrt(2)) = 1.0!
    i_rad = np.radians(np.clip(takeoff_lower, 0.0, 90.0))
    r = np.sqrt(2.0) * np.sin(i_rad / 2.0)

    az_rad = np.radians(azimuth)
    x = r * np.sin(az_rad)
    y = r * np.cos(az_rad)
    return x, y


def get_nodal_plane_points(strike, dip):
    """
    Calculate (x, y) coordinates on the lower-hemisphere stereonet for a nodal plane.
    A plane of strike phi and dip delta intersects the lower hemisphere in a circular arc.
    """
    # Rake variation along the fault plane from -180 to 180 (or angle from 0 to 180)
    # The normal to the plane has dip delta, azimuth phi + 90
    phi = np.radians(strike)
    delta = np.radians(dip)

    # Parametrize points along the great circle arc on the lower hemisphere
    # Ray vector on plane: r = cos(psi)*s + sin(psi)*d
    # where s is along strike [cos(phi), sin(phi), 0]
    # and d is down dip [-cos(delta)*sin(phi), cos(delta)*cos(phi), sin(delta)]
    psi = np.linspace(0, np.pi, 100)

    r1 = np.cos(psi) * np.cos(phi) - np.sin(psi) * np.cos(delta) * np.sin(phi)
    r2 = np.cos(psi) * np.sin(phi) + np.sin(psi) * np.cos(delta) * np.cos(phi)
    r3 = np.sin(psi) * np.sin(delta)  # down component >= 0

    # Azimuth and takeoff angle
    az = np.degrees(np.arctan2(r2, r1)) % 360.0
    # r3 is positive downwards, so takeoff angle = arccos(r3)
    to = np.degrees(np.arccos(np.clip(r3, 0.0, 1.0)))

    xs, ys = to_stereonet_coords(az, to)
    return xs, ys


def plot_beachball(
    strike,
    dip,
    rake,
    station_evaluations=None,
    p_axis=None,
    t_axis=None,
    all_solutions=None,
    ax=None,
    facecolor="#16a085",  # Dark cyan / teal (matching SurfQuake style)
    title="Focal Mechanism (FOCMEC)",
):
    """
    Render focal mechanism beachball with station polarities and P/T axes.
    
    Parameters
    ----------
    strike, dip, rake : float
        Primary fault plane orientation in degrees.
    station_evaluations : list of dict, optional
        Station data with keys 'station', 'azimuth', 'takeoff', 'observed', 'calculated', 'is_misfit'.
    p_axis, t_axis : tuple (trend, plunge), optional
        P and T kinematic axes.
    all_solutions : list of dict, optional
        Ensemble of acceptable solutions to plot as thin uncertainty arcs.
    ax : matplotlib.axes.Axes, optional
        Target axes. If None, a new figure is created.
    facecolor : str
        Color for compressional quadrants.
    title : str
        Figure title.
        
    Returns
    -------
    fig, ax
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(6.5, 6.5), dpi=100)
    else:
        fig = ax.figure

    ax.clear()
    ax.set_aspect("equal")
    ax.axis("off")

    # 1. Base focal sphere circle (radius = 1.0)
    focal_circle = Circle((0, 0), 1.0, facecolor="white", edgecolor="black", linewidth=2.0, zorder=1)
    ax.add_patch(focal_circle)

    # 2. Shaded compressional quadrants using high-resolution grid evaluation
    grid_n = 250
    x_lin = np.linspace(-1.0, 1.0, grid_n)
    y_lin = np.linspace(-1.0, 1.0, grid_n)
    xx, yy = np.meshgrid(x_lin, y_lin)
    rr = np.sqrt(xx**2 + yy**2)

    # Invert Schmidt projection: r = sqrt(2)*sin(i/2) => sin(i/2) = r / sqrt(2)
    # => i = 2 * arcsin(r / sqrt(2))
    sin_half_i = np.clip(rr / np.sqrt(2.0), 0.0, 1.0)
    ii = 2.0 * np.arcsin(sin_half_i)  # in radians
    # azimuth = arctan2(x, y)
    aa = np.arctan2(xx, yy)  # in radians (from North)

    r1 = np.sin(ii) * np.cos(aa)
    r2 = np.sin(ii) * np.sin(aa)
    r3 = np.cos(ii)

    # Normal n and slip u
    from .kinematics import strike_dip_rake_to_vectors
    n, u = strike_dip_rake_to_vectors(strike, dip, rake)

    n_dot_r = n[0] * r1 + n[1] * r2 + n[2] * r3
    u_dot_r = u[0] * r1 + u[1] * r2 + u[2] * r3
    radiation_amp = n_dot_r * u_dot_r

    # Mask outside the focal sphere
    radiation_amp[rr > 1.0] = np.nan

    # Fill compressional quadrant (> 0)
    ax.contourf(
        xx, yy, radiation_amp,
        levels=[0.0, 1e9],
        colors=[facecolor],
        alpha=0.85,
        zorder=2,
    )

    # 3. Plot ensemble of acceptable solutions (uncertainty arcs)
    if all_solutions and len(all_solutions) > 1:
        # Plot up to 60 solutions to maintain high performance and clean visual
        sample_sols = all_solutions[:60]
        for sol in sample_sols:
            s1, d1 = sol["strike"], sol["dip"]
            s2, d2 = sol.get("strike2", 0.0), sol.get("dip2", 0.0)
            xs1, ys1 = get_nodal_plane_points(s1, d1)
            xs2, ys2 = get_nodal_plane_points(s2, d2)
            ax.plot(xs1, ys1, color="#7f8c8d", alpha=0.35, linewidth=0.8, zorder=3)
            ax.plot(xs2, ys2, color="#7f8c8d", alpha=0.35, linewidth=0.8, zorder=3)

    # 4. Primary and Auxiliary Nodal Planes (Thick black lines)
    from .kinematics import fault_plane_to_auxiliary
    s2, d2, _ = fault_plane_to_auxiliary(strike, dip, rake)
    xp1, yp1 = get_nodal_plane_points(strike, dip)
    xp2, yp2 = get_nodal_plane_points(s2, d2)
    ax.plot(xp1, yp1, color="black", linewidth=2.2, zorder=4, label="Nodal Plane 1")
    ax.plot(xp2, yp2, color="black", linewidth=2.2, linestyle="-", zorder=4, label="Nodal Plane 2")

    # 5. P and T axes markers
    if p_axis is not None:
        px, py = to_stereonet_coords(p_axis[0], p_axis[1])
        ax.plot(px, py, "o", color="white", markeredgecolor="black", markeredgewidth=1.5, markersize=10, zorder=6)
        ax.text(px, py, "P", color="black", fontsize=8, fontweight="bold", ha="center", va="center", zorder=7)

    if t_axis is not None:
        tx, ty = to_stereonet_coords(t_axis[0], t_axis[1])
        ax.plot(tx, ty, "o", color="black", markeredgecolor="white", markeredgewidth=1.5, markersize=10, zorder=6)
        ax.text(tx, ty, "T", color="white", fontsize=8, fontweight="bold", ha="center", va="center", zorder=7)

    # 6. Station First-Motion Polarities
    if station_evaluations:
        for s in station_evaluations:
            sta = s.get("station", "")
            az = s.get("azimuth", 0.0)
            to = s.get("takeoff", 0.0)
            obs = s.get("observed", 0)
            misfit = s.get("is_misfit", False)

            # Map upgoing rays to lower hemisphere
            if to > 90.0:
                to_lower = 180.0 - to
                az_lower = (az + 180.0) % 360.0
            else:
                to_lower = to
                az_lower = az % 360.0

            sx, sy = to_stereonet_coords(az_lower, to_lower)

            if obs > 0:
                # Compression (+) -> Upward triangle
                marker = "^"
                mcolor = "#e74c3c" if not misfit else "#f39c12"  # Red, or Orange/Yellow if misfit
                edgecolor = "#962d00" if not misfit else "#d35400"
            else:
                # Dilatation (-) -> Downward triangle
                marker = "v"
                mcolor = "#2980b9" if not misfit else "#f39c12"  # Blue, or Orange/Yellow if misfit
                edgecolor = "#1a5276" if not misfit else "#d35400"

            size = 80 if not misfit else 110
            linewidth = 1.2 if not misfit else 2.5

            ax.scatter(
                sx, sy,
                marker=marker,
                s=size,
                facecolors=mcolor,
                edgecolors="black" if not misfit else "#f1c40f",
                linewidths=linewidth,
                zorder=8,
            )

            # Station label
            ax.text(
                sx + 0.03, sy + 0.02,
                sta,
                fontsize=7.5,
                fontweight="bold" if misfit else "normal",
                color="#c0392b" if misfit else "#2c3e50",
                zorder=9,
            )

    # Cardinal directions (N, S, E, W)
    ax.text(0, 1.07, "N", fontsize=11, fontweight="bold", ha="center", va="center", zorder=10)
    ax.text(0, -1.07, "S", fontsize=10, ha="center", va="center", color="#7f8c8d", zorder=10)
    ax.text(1.07, 0, "E", fontsize=10, ha="center", va="center", color="#7f8c8d", zorder=10)
    ax.text(-1.07, 0, "W", fontsize=10, ha="center", va="center", color="#7f8c8d", zorder=10)

    # Center tick
    ax.plot(0, 0, "+", color="black", markersize=6, zorder=5)

    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)

    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", pad=14)

    fig.tight_layout()
    return fig, ax


def save_beachball_figure(fig, file_path, dpi=300):
    """Save matplotlib beachball figure to file (PNG, PDF, SVG)."""
    fig.savefig(file_path, dpi=dpi, bbox_inches="tight")
