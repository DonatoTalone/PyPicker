"""
Plugin for earthquake location using hypo71py in PyPicker.
Bridges PyPicker picks and ObsPy Stream SAC headers to hypo71py solver.
"""

from copy import deepcopy
from pathlib import Path
import numpy as np
from obspy import UTCDateTime

import sys
_plugins_dir = str(Path(__file__).resolve().parent)
if _plugins_dir not in sys.path:
    sys.path.insert(0, _plugins_dir)

from hypo71py import SINGLE, Station, CrustalVelocityModel, PhasePick


def extract_stations_and_picks(stream, picks):
    """
    Extract station metadata and phase picks for hypo71py.

    Parameters
    ----------
    stream : obspy.Stream
        Stream with SAC headers (containing stla, stlo, stel).
    picks : list of dict
        PyPicker pick records with keys: sta, phase, abs_t, uncertainty, etc.

    Returns
    -------
    tuple (stations, pick_dict, missing_stations)
        stations : list of Station
        pick_dict : dict of {sta: {phase: PhasePick}}
        missing_stations : list of station codes missing coordinates
    """
    station_meta = {}
    for tr in stream:
        sta = tr.stats.station
        if sta in station_meta:
            continue
        sac = getattr(tr.stats, "sac", {})
        stla = sac.get("stla")
        stlo = sac.get("stlo")
        stel = sac.get("stel", 0.0)
        if stel == -12345.0 or stel is None:
            stel = 0.0

        if stla is not None and stlo is not None and stla != -12345.0 and stlo != -12345.0:
            elev_km = float(stel) / 1000.0  # HYPO71 expects km
            station_meta[sta] = Station(
                code=sta,
                lon=float(stlo),
                lat=float(stla),
                elevation=float(elev_km),
                depth=0.0,
            )

    pick_dict = {}
    missing_stations = set()

    for pk in picks:
        sta = pk.get("sta")
        phase = pk.get("phase", "").upper()
        if phase not in ("P", "S"):
            continue

        if sta not in station_meta:
            missing_stations.add(sta)
            continue

        abs_t = UTCDateTime(pk["abs_t"])
        unc = float(pk.get("uncertainty", 0.0))

        onset = pk.get("onset", "")
        polarity = pk.get("polarity", "")

        phase_pick = PhasePick(
            phase_name=phase,
            datetime=abs_t,
            station_code=sta,
            onset=onset,
            first_motion=polarity,
            include_in_loc=True,
        )

        if sta not in pick_dict:
            pick_dict[sta] = {}
        # Keep earliest or most confident pick if duplicated
        if phase not in pick_dict[sta]:
            pick_dict[sta][phase] = phase_pick
        else:
            existing = pick_dict[sta][phase]
            if unc < getattr(existing, "uncertainty", unc):
                pick_dict[sta][phase] = phase_pick

    stations = [station_meta[s] for s in pick_dict if s in station_meta]
    return stations, pick_dict, list(missing_stations)


def build_crustal_velocity_model(model_data):
    """
    Construct a hypo71py CrustalVelocityModel from dictionary loaded from velocity_model.json.
    """
    name = model_data.get("name", "1D Model")
    layers = model_data.get("layers", [])
    if not layers:
        raise ValueError("Velocity model must have at least one layer.")

    depths = [float(l["depth_km"]) for l in layers]
    vps = [float(l["vp"]) for l in layers]
    vp_vs = float(model_data.get("vp_vs_ratio", 1.73))

    vss = []
    for l, vp in zip(layers, vps):
        if "vs" in l and l["vs"] is not None and float(l["vs"]) > 0:
            vss.append(float(l["vs"]))
        else:
            vss.append(vp / vp_vs)

    return CrustalVelocityModel(
        depths=np.array(depths, dtype=float),
        VP=np.array(vps, dtype=float),
        VS=np.array(vss, dtype=float),
        name=name,
    )


def run_hypo71_localization(
    stream,
    picks,
    velocity_model=None,
    ztr=5.0,
    trial_origin=None,
    verbose=False,
):
    """
    Run hypo71py SINGLE earthquake location algorithm.

    Parameters
    ----------
    stream : obspy.Stream
        Waveform stream containing station SAC coordinates.
    picks : list of dict
        Picks list from PyPicker.
    velocity_model : dict or CrustalVelocityModel or None
        Velocity model data (if None or dict, loaded/converted).
    ztr : float
        Trial focal depth in km (default: 5.0).
    trial_origin : tuple (lon, lat, origin_time) or None
        Initial trial origin. If None, estimated from earliest pick.
    verbose : bool
        Whether to print verbose output.

    Returns
    -------
    dict
        Structured location results including hypocenter, uncertainties, and residuals.
    """
    stations, pick_dict, missing_stations = extract_stations_and_picks(stream, picks)

    total_phases = sum(len(ph) for ph in pick_dict.values())
    if total_phases < 4:
        raise ValueError(
            f"Insufficient phase picks for location. At least 4 picks are required (found {total_phases})."
        )
    if len(stations) < 3:
        raise ValueError(
            f"Picks must span at least 3 stations with known coordinates (found {len(stations)})."
        )

    # Velocity model preparation
    if isinstance(velocity_model, CrustalVelocityModel):
        vmod = velocity_model
    elif isinstance(velocity_model, dict):
        vmod = build_crustal_velocity_model(velocity_model)
    else:
        import picker_utils_qt as utils
        vmod_dict = utils.load_velocity_model()
        vmod = build_crustal_velocity_model(vmod_dict)

    # Estimate initial trial origin if not provided
    if trial_origin is None:
        earliest_t = None
        earliest_sta = None
        for sta, phases in pick_dict.items():
            for ph, p_obj in phases.items():
                if earliest_t is None or p_obj.datetime < earliest_t:
                    earliest_t = p_obj.datetime
                    earliest_sta = sta

        nearest_stat = next(s for s in stations if s.code == earliest_sta)
        v0 = vmod.VP[0] if len(vmod.VP) > 0 else 5.0
        trial_t = earliest_t - (ztr / v0)
        trial_origin = (nearest_stat.lon, nearest_stat.lat, trial_t)

    # Execute hypo71 SINGLE solver
    loc = SINGLE(
        stations,
        pick_dict,
        vmod,
        ZTR=float(ztr),
        origin=trial_origin,
        use_fortran_speedups=False,
        verbose=verbose,
    )

    lon, lat, depth, time, se, sp, qsd, ni, rms = loc

    # Parse standard errors: [ERH, ERZ, ...]
    erh = float(se[0]) if len(se) > 0 and not np.isnan(se[0]) else 0.0
    erz = float(se[1]) if len(se) > 1 and not np.isnan(se[1]) else 0.0

    # Build residuals list
    residuals = []
    df = getattr(sp, "data", None)
    if df is not None:
        for _, row in df.iterrows():
            code = str(row.get("code", ""))
            repi = float(row.get("Repi", 0.0))
            az = float(row.get("azimuth", 0.0))

            # P phase
            if not np.isnan(row.get("Pres", np.nan)) or row.get("Ptime") is not None:
                p_obs = row.get("Ptime")
                p_res = row.get("Pres")
                p_wt = row.get("Ptot_weight", 0.0)
                if p_obs is not None and not (isinstance(p_obs, float) and np.isnan(p_obs)):
                    p_obs_utc = UTCDateTime(p_obs)
                    p_calc = p_obs_utc - float(p_res) if not np.isnan(p_res) else None
                    residuals.append({
                        "station": code,
                        "phase": "P",
                        "observed_time": p_obs_utc,
                        "calculated_time": p_calc,
                        "residual_sec": float(p_res) if not np.isnan(p_res) else None,
                        "distance_km": repi,
                        "azimuth_deg": az,
                        "weight": float(p_wt),
                    })

            # S phase
            if not np.isnan(row.get("Sres", np.nan)) or row.get("Stime") is not None:
                s_obs = row.get("Stime")
                s_res = row.get("Sres")
                s_wt = row.get("Stot_weight", 0.0)
                if s_obs is not None and not (isinstance(s_obs, float) and np.isnan(s_obs)):
                    s_obs_utc = UTCDateTime(s_obs)
                    s_calc = s_obs_utc - float(s_res) if not np.isnan(s_res) else None
                    residuals.append({
                        "station": code,
                        "phase": "S",
                        "observed_time": s_obs_utc,
                        "calculated_time": s_calc,
                        "residual_sec": float(s_res) if not np.isnan(s_res) else None,
                        "distance_km": repi,
                        "azimuth_deg": az,
                        "weight": float(s_wt),
                    })

    # Sort residuals by station and phase
    residuals.sort(key=lambda r: (r["station"], r["phase"]))

    return {
        "latitude": float(lat),
        "longitude": float(lon),
        "depth_km": float(depth),
        "origin_time": UTCDateTime(time),
        "rms": float(rms) if not np.isnan(rms) else 0.0,
        "erh": erh,
        "erz": erz,
        "quality": str(qsd) if qsd else "--",
        "iterations": int(ni),
        "phases_used": int(sp.num_phases),
        "stations_used": int(sp.num_stations),
        "residuals": residuals,
        "missing_stations": missing_stations,
        "velocity_model_name": getattr(vmod, "name", "1D Model"),
    }
