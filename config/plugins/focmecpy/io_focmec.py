"""
Input/Output utilities for FOCMEC:
- Generating and reading standard FOCMEC .inp and .lst files (SurfQuake / Snoke compatible)
- Exporting complete earthquake localization and focal mechanism inversion parameters to CSV
"""

import csv
from pathlib import Path
from obspy import UTCDateTime


def write_focmec_inp(file_path, comment, stations, azimuths, takeoff_angles, polarities):
    """
    Write standard FOCMEC input file (.inp).
    
    Format:
    Line 1: Comment / Header line
    Data lines: STA (4 chars), AZ (8.2f), TOANG (8.2f), SENSE ('C' or 'D')
    
    Parameters
    ----------
    file_path : str or Path
        Target .inp file path.
    comment : str
        Header/comment line.
    stations : list of str
        Station names.
    azimuths : list of float
        Source-to-station azimuths in degrees.
    takeoff_angles : list of float
        Take-off angles in degrees.
    polarities : list of int or str
        Polarities (+1 / 'C' / 'U' for compression, -1 / 'D' for dilatation).
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{comment.strip()}\n")
        for sta, az, to, pol in zip(stations, azimuths, takeoff_angles, polarities):
            # Clean station name (max 4-5 chars for standard FOCMEC)
            sta_str = str(sta)[:4].ljust(4)
            if pol in (1, "+", "U", "C", "positive"):
                sense = "C"
            elif pol in (-1, "-", "D", "negative"):
                sense = "D"
            else:
                continue
            # Format: A4, 2F8.2, 1X, A1
            f.write(f"{sta_str}  {float(az):7.2f} {float(to):7.2f} {sense}\n")
        f.write("\n")  # Empty line terminator


def read_focmec_inp(file_path):
    """
    Read standard FOCMEC .inp file.
    
    Returns
    -------
    comment : str
    station_data : list of dict (station, azimuth, takeoff, polarity)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"FOCMEC input file not found: {path}")

    station_data = []
    comment = ""
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.rstrip() for line in f if line.strip()]

    if lines:
        comment = lines[0]
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                sta = parts[0]
                try:
                    az = float(parts[1])
                    to = float(parts[2])
                    sense = parts[3].upper()
                    pol = 1 if sense in ("C", "U", "+") else (-1 if sense in ("D", "-") else 0)
                    station_data.append({
                        "station": sta,
                        "azimuth": az,
                        "takeoff": to,
                        "sense": sense,
                        "polarity": pol,
                    })
                except ValueError:
                    continue

    return comment, station_data


def export_focal_mechanism_to_csv(
    file_path,
    localization_info,
    focmec_results,
):
    """
    Export earthquake localization and focal mechanism solution to CSV.
    
    Parameters
    ----------
    file_path : str or Path
        Target CSV output path.
    localization_info : dict
        Earthquake hypocenter details (latitude, longitude, depth_km, origin_time, rms, erh, erz, quality).
    focmec_results : dict
        Results dictionary returned by solve_focal_mechanism.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    best = focmec_results.get("best_solution", {})
    p_ax = best.get("p_axis", (0.0, 0.0))
    t_ax = best.get("t_axis", (0.0, 0.0))
    b_ax = best.get("b_axis", (0.0, 0.0))

    ot = localization_info.get("origin_time")
    ot_str = ot.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if isinstance(ot, UTCDateTime) else str(ot)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Section 1: Event Summary
        writer.writerow(["# --- PYPICKER EARTHQUAKE & FOCAL MECHANISM REPORT ---"])
        writer.writerow([])
        writer.writerow(["--- HYPOCENTER LOCALIZATION PARAMETERS ---"])
        writer.writerow(["Origin_Time_UTC", ot_str])
        writer.writerow(["Latitude_deg", f"{localization_info.get('latitude', 0.0):.4f}"])
        writer.writerow(["Longitude_deg", f"{localization_info.get('longitude', 0.0):.4f}"])
        writer.writerow(["Depth_km", f"{localization_info.get('depth_km', 0.0):.2f}"])
        writer.writerow(["RMS_sec", f"{localization_info.get('rms', 0.0):.3f}"])
        writer.writerow(["ERH_km", f"{localization_info.get('erh', 0.0):.2f}"])
        writer.writerow(["ERZ_km", f"{localization_info.get('erz', 0.0):.2f}"])
        writer.writerow(["Quality_Code", localization_info.get("quality", "--")])
        writer.writerow(["Velocity_Model", localization_info.get("velocity_model_name", "1D Model")])
        writer.writerow([])

        # Section 2: Focal Mechanism Solution
        writer.writerow(["--- FOCAL MECHANISM SOLUTION (FOCMEC) ---"])
        writer.writerow(["Faulting_Regime", best.get("regime", "Unknown")])
        writer.writerow(["NP1_Strike_deg", f"{best.get('strike', 0.0):.1f}"])
        writer.writerow(["NP1_Dip_deg", f"{best.get('dip', 0.0):.1f}"])
        writer.writerow(["NP1_Rake_deg", f"{best.get('rake', 0.0):.1f}"])
        writer.writerow(["NP2_Strike_deg", f"{best.get('strike2', 0.0):.1f}"])
        writer.writerow(["NP2_Dip_deg", f"{best.get('dip2', 0.0):.1f}"])
        writer.writerow(["NP2_Rake_deg", f"{best.get('rake2', 0.0):.1f}"])
        writer.writerow(["P_Axis_Trend_deg", f"{p_ax[0]:.1f}"])
        writer.writerow(["P_Axis_Plunge_deg", f"{p_ax[1]:.1f}"])
        writer.writerow(["T_Axis_Trend_deg", f"{t_ax[0]:.1f}"])
        writer.writerow(["T_Axis_Plunge_deg", f"{t_ax[1]:.1f}"])
        writer.writerow(["B_Axis_Trend_deg", f"{b_ax[0]:.1f}"])
        writer.writerow(["B_Axis_Plunge_deg", f"{b_ax[1]:.1f}"])
        writer.writerow([])

        # Section 3: Inversion Quality & Solver Statistics
        writer.writerow(["--- INVERSION STATISTICS ---"])
        writer.writerow(["Polarities_Count", focmec_results.get("num_polarities", 0)])
        writer.writerow(["Misfits_Count", focmec_results.get("min_misfit", 0)])
        writer.writerow(["Max_Allowed_Errors", focmec_results.get("max_errors_allowed", 0)])
        writer.writerow(["Acceptable_Solutions_Count", focmec_results.get("num_acceptable", 0)])
        writer.writerow(["Azimuthal_Gap_deg", f"{focmec_results.get('azimuthal_gap', 0.0):.1f}"])
        writer.writerow(["Grid_Step_deg", f"{focmec_results.get('grid_step', 5.0):.1f}"])
        writer.writerow([])

        # Section 4: Station Polarities Table
        writer.writerow(["--- STATION POLARITIES & FIT ---"])
        writer.writerow([
            "Station",
            "Azimuth_deg",
            "Takeoff_deg",
            "Observed_Polarity",
            "Calculated_Polarity",
            "Misfit_Flag"
        ])
        for s in focmec_results.get("station_evaluations", []):
            obs_label = "Compression (+)" if s["observed"] > 0 else ("Dilatation (-)" if s["observed"] < 0 else "None")
            calc_label = "Compression (+)" if s["calculated"] > 0 else ("Dilatation (-)" if s["calculated"] < 0 else "None")
            misfit_str = "MISFIT" if s["is_misfit"] else "OK"
            writer.writerow([
                s["station"],
                f"{s['azimuth']:.1f}",
                f"{s['takeoff']:.1f}",
                obs_label,
                calc_label,
                misfit_str,
            ])
