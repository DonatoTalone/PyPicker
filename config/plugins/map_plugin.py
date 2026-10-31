"""
PyPicker Plugin: Geographic Map with DEM Relief, Seismic Stations, and Hypocenter.

Features:
- Cartopy map projection with country borders, coastlines, oceans, lakes.
- Digital Elevation Model (DEM) with shaded relief and adjustable transparency.
- Full background station inventory from configured FDSN client (default INGV).
- Distinct highlighting and labeling for active stations currently open in PyPicker.
- Epicenter marker displayed dynamically when event coordinates are present
  or computed via Hypo71 localization.
- Pan and zoom navigation via standard Qt navigation toolbar and mouse wheel.
"""

import logging
from pathlib import Path
import urllib.request

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
import numpy as np

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.img_tiles as cimgt

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

try:
    import picker_utils_qt as utils
except ImportError:
    import config.picker_utils_qt as utils

logger = logging.getLogger(__name__)


class EsriShadedRelief(cimgt.GoogleTiles):
    """Esri World Shaded Relief tile provider for topographic DEM hillshading."""

    def _image_url(self, tile):
        x, y, z = tile
        return f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Shaded_Relief/MapServer/tile/{z}/{y}/{x}"


class MapDialog(QDialog):
    """
    Interactive geographic map window displaying seismic stations, DEM relief,
    national borders, and earthquake epicenter.
    """

    location_updated = pyqtSignal(float, float, float, object)

    def __init__(self, stream=None, parent=None, client_name=None):
        super().__init__(parent)
        self.setWindowTitle("PyPicker - Seismic Network & Event Map")
        if hasattr(utils, "get_app_icon"):
            self.setWindowIcon(utils.get_app_icon("dark"))
        self.resize(980, 750)

        self.stream = stream
        self.config = utils.load_config() if hasattr(utils, "load_config") else {}
        defaults = self.config.get("defaults", {})

        self.client_name = client_name or defaults.get("station_client", "INGV")
        self.dem_alpha = float(defaults.get("map_dem_alpha", 0.40))
        self.show_all_stations = bool(defaults.get("map_show_all_stations", True))
        self.show_dem = True
        self.show_labels = True

        self.event_coords = None  # (lat, lon, depth_km, origin_time)
        self.focal_mechanism = None  # best solution dict or (strike, dip, rake)
        self.inventory = None
        self.station_index = {}
        tile_cache = utils.get_cache_dir() / "tiles"
        try:
            tile_cache.mkdir(parents=True, exist_ok=True)
            self.tile_provider = EsriShadedRelief(cache=tile_cache)
        except Exception:
            self.tile_provider = EsriShadedRelief()

        self._init_ui()
        self._load_stations()
        self.refresh_map(initial=True)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Control Toolbar
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(10)

        # Client selection
        ctrl_bar.addWidget(QLabel("<b>FDSN Client:</b>"))
        self.client_combo = QComboBox()
        self.client_combo.setEditable(True)
        common_clients = ["INGV", "IRIS", "ETH", "RESIF", "GEONET", "USGS", "GEOFON", "BGR", "NIEP"]
        self.client_combo.addItems(common_clients)
        if self.client_name in common_clients:
            self.client_combo.setCurrentText(self.client_name)
        else:
            self.client_combo.setEditText(self.client_name)
        self.client_combo.currentTextChanged.connect(self._on_client_changed)
        ctrl_bar.addWidget(self.client_combo)

        self.btn_refresh = QPushButton("Refresh Stations")
        self.btn_refresh.setToolTip("Reload station inventory from FDSN client")
        self.btn_refresh.clicked.connect(self._on_refresh_stations_clicked)
        ctrl_bar.addWidget(self.btn_refresh)

        ctrl_bar.addSpacing(10)

        # Checkbox: show all stations
        self.chk_all_sta = QCheckBox("Show All Stations")
        self.chk_all_sta.setChecked(self.show_all_stations)
        self.chk_all_sta.toggled.connect(self._on_toggle_all_stations)
        ctrl_bar.addWidget(self.chk_all_sta)

        # Checkbox: show labels
        self.chk_labels = QCheckBox("Labels")
        self.chk_labels.setChecked(self.show_labels)
        self.chk_labels.toggled.connect(self._on_toggle_labels)
        ctrl_bar.addWidget(self.chk_labels)

        # Checkbox: show DEM
        self.chk_dem = QCheckBox("DEM Relief")
        self.chk_dem.setChecked(self.show_dem)
        self.chk_dem.toggled.connect(self._on_toggle_dem)
        ctrl_bar.addWidget(self.chk_dem)

        # DEM Transparency slider
        ctrl_bar.addWidget(QLabel("DEM Alpha:"))
        self.slider_dem = QSlider(Qt.Orientation.Horizontal)
        self.slider_dem.setRange(5, 100)
        self.slider_dem.setValue(int(self.dem_alpha * 100))
        self.slider_dem.setFixedWidth(90)
        self.slider_dem.setToolTip("DEM Transparency / Opacity")
        self.slider_dem.valueChanged.connect(self._on_slider_alpha_changed)
        ctrl_bar.addWidget(self.slider_dem)

        self.lbl_alpha = QLabel(f"{int(self.dem_alpha * 100)}%")
        ctrl_bar.addWidget(self.lbl_alpha)

        ctrl_bar.addStretch()

        # Center on active stations
        self.btn_center = QPushButton("Fit Extent")
        self.btn_center.setToolTip("Reset extent to focus on active stations and event")
        self.btn_center.clicked.connect(lambda: self.refresh_map(initial=True))
        ctrl_bar.addWidget(self.btn_center)

        layout.addLayout(ctrl_bar)

        # Matplotlib Figure & Cartopy Canvas
        self.fig = plt.Figure(figsize=(9, 7), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        # Connect mouse wheel for zoom
        self.canvas.mpl_connect("scroll_event", self._on_scroll_zoom)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)

        # Status Bar
        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        layout.addWidget(self.status_bar)

    def _load_stations(self, force_refresh=False):
        """Load station inventory from cache or FDSN client."""
        self.status_bar.showMessage(f"Loading station inventory from client '{self.client_name}'...")
        try:
            self.inventory = utils.get_station_inventory(self.client_name, force_refresh=force_refresh)
            self.station_index = utils.build_station_index(self.inventory)
            total = len(self.station_index)
            self.status_bar.showMessage(f"Client '{self.client_name}': {total} stations available.", 4000)
        except Exception as e:
            logger.warning(f"Failed to load station inventory: {e}")
            self.inventory = None
            self.station_index = {}
            self.status_bar.showMessage(f"Could not load stations from '{self.client_name}': {e}", 5000)

    def _on_client_changed(self, text):
        new_client = text.strip().upper()
        if new_client and new_client != self.client_name:
            self.client_name = new_client
            self._load_stations(force_refresh=False)
            self.refresh_map(initial=False)

    def _on_refresh_stations_clicked(self):
        self._load_stations(force_refresh=True)
        self.refresh_map(initial=False)

    def _on_toggle_all_stations(self, checked):
        self.show_all_stations = checked
        self.refresh_map(initial=False)

    def _on_toggle_labels(self, checked):
        self.show_labels = checked
        self.refresh_map(initial=False)

    def _on_toggle_dem(self, checked):
        self.show_dem = checked
        self.refresh_map(initial=False)

    def _on_slider_alpha_changed(self, val):
        self.dem_alpha = val / 100.0
        self.lbl_alpha.setText(f"{val}%")
        self.refresh_map(initial=False)

    def _on_scroll_zoom(self, event):
        """Zoom in or out centered on cursor position."""
        if event.inaxes != self.ax:
            return

        scale_factor = 0.8 if event.button == "up" else 1.25

        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        xdata = event.xdata
        ydata = event.ydata
        if xdata is None or ydata is None:
            return

        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

        rel_x = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rel_y = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])

        new_xmin = xdata - new_width * (1.0 - rel_x)
        new_xmax = xdata + new_width * rel_x
        new_ymin = ydata - new_height * (1.0 - rel_y)
        new_ymax = ydata + new_height * rel_y

        self.ax.set_extent([new_xmin, new_xmax, new_ymin, new_ymax], crs=ccrs.PlateCarree())
        self.canvas.draw_idle()

    def update_stream(self, stream):
        """Update active waveform stream and redraw."""
        self.stream = stream
        if self.stream and self.station_index:
            utils.autofill_missing_station_coordinates(self.stream, self.station_index)
        self.refresh_map(initial=True)

    def update_event_location(self, evla, evlo, depth_km=None, origin_time=None):
        """Dynamically update epicenter marker and redraw without resetting zoom."""
        if evla is not None and evlo is not None and evla != -12345.0 and evlo != -12345.0:
            self.event_coords = (float(evla), float(evlo), depth_km, origin_time)
        else:
            self.event_coords = None
        self.refresh_map(initial=False)

    def update_focal_mechanism(self, focal_mechanism):
        """Dynamically update focal mechanism solution and redraw."""
        self.focal_mechanism = focal_mechanism
        self.refresh_map(initial=False)

    def extract_active_stations(self):
        """Extract station coordinates for currently loaded stream traces."""
        active = {}
        if not self.stream:
            return active

        for tr in self.stream:
            sta = tr.stats.station.upper()
            if sta in active:
                continue

            sac = getattr(tr.stats, "sac", None)
            stla = sac.get("stla") if sac else None
            stlo = sac.get("stlo") if sac else None
            stel = sac.get("stel", 0.0) if sac else 0.0

            if stla is not None and stlo is not None and stla != -12345.0 and stlo != -12345.0:
                active[sta] = (float(stla), float(stlo), float(stel))
            elif self.station_index and sta in self.station_index:
                info = self.station_index[sta]
                active[sta] = (float(info["latitude"]), float(info["longitude"]), float(info["elevation"]))

        return active

    def extract_event_coordinates(self):
        """Detect event coordinates from stream or previous localization."""
        if self.event_coords is not None:
            return self.event_coords

        if not self.stream:
            return None

        for tr in self.stream:
            sac = getattr(tr.stats, "sac", None)
            if not sac:
                continue
            evla = sac.get("evla")
            evlo = sac.get("evlo")
            if evla is not None and evlo is not None and evla != -12345.0 and evlo != -12345.0:
                depth_km = sac.get("evdp")
                if depth_km == -12345.0:
                    depth_km = None
                return (float(evla), float(evlo), depth_km, None)

        return None

    def refresh_map(self, initial=False):
        """Redraw map layers, stations, DEM and event marker."""
        prev_extent = None
        if not initial and hasattr(self, "ax") and self.ax is not None:
            try:
                prev_extent = self.ax.get_extent(crs=ccrs.PlateCarree())
            except Exception:
                prev_extent = None

        self.fig.clear()
        self.ax = self.fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())

        active_stations = self.extract_active_stations()
        event_info = self.extract_event_coordinates()

        # Determine extent
        if prev_extent is not None:
            extent = prev_extent
        else:
            lats = [c[0] for c in active_stations.values()]
            lons = [c[1] for c in active_stations.values()]
            if event_info:
                lats.append(event_info[0])
                lons.append(event_info[1])

            if lats and lons:
                min_lat, max_lat = min(lats), max(lats)
                min_lon, max_lon = min(lons), max(lons)
                dlat = max(max_lat - min_lat, 0.4)
                dlon = max(max_lon - min_lon, 0.4)
                extent = [
                    min_lon - dlon * 0.4,
                    max_lon + dlon * 0.4,
                    min_lat - dlat * 0.4,
                    max_lat + dlat * 0.4,
                ]
            else:
                # Default extent: Italy and Central Mediterranean
                extent = [6.0, 19.5, 35.5, 47.5]

        self.ax.set_extent(extent, crs=ccrs.PlateCarree())

        # Layer 1: DEM Relief
        if self.show_dem:
            try:
                # Determine suitable tile zoom level based on extent span
                lon_span = abs(extent[1] - extent[0])
                if lon_span > 20:
                    zoom = 4
                elif lon_span > 6:
                    zoom = 6
                elif lon_span > 2:
                    zoom = 8
                elif lon_span > 0.5:
                    zoom = 10
                else:
                    zoom = 11

                self.ax.add_image(self.tile_provider, zoom, alpha=self.dem_alpha)
            except Exception as e:
                logger.debug(f"Tile provider unavailable ({e}), using Natural Earth stock image.")
                try:
                    self.ax.stock_img()
                except Exception:
                    pass

        # Layer 2: Vector geographic features
        try:
            feat_scale = "50m" if abs(extent[1] - extent[0]) > 6 else "10m"
            self.ax.add_feature(
                cfeature.OCEAN.with_scale(feat_scale),
                facecolor="#d4e6f1",
                alpha=0.35,
                zorder=2,
            )
            self.ax.add_feature(
                cfeature.LAKES.with_scale(feat_scale),
                facecolor="#d4e6f1",
                alpha=0.45,
                zorder=2,
            )
            self.ax.add_feature(
                cfeature.COASTLINE.with_scale(feat_scale),
                edgecolor="#2c3e50",
                linewidth=0.8,
                zorder=3,
            )
            self.ax.add_feature(
                cfeature.BORDERS.with_scale(feat_scale),
                linestyle=":",
                edgecolor="#34495e",
                linewidth=0.9,
                zorder=3,
            )
        except Exception as e:
            logger.warning(f"Error drawing natural earth features: {e}")

        # Layer 3: Gridlines
        try:
            gl = self.ax.gridlines(
                draw_labels=True,
                linewidth=0.5,
                color="gray",
                alpha=0.4,
                linestyle="--",
            )
            gl.top_labels = False
            gl.right_labels = False
        except Exception:
            pass

        # Layer 4: Background FDSN Client Stations
        if self.show_all_stations and self.station_index:
            bg_lons = []
            bg_lats = []
            active_names = set(active_stations.keys())
            for code, info in self.station_index.items():
                if code not in active_names:
                    bg_lons.append(info["longitude"])
                    bg_lats.append(info["latitude"])

            if bg_lons:
                self.ax.scatter(
                    bg_lons,
                    bg_lats,
                    marker="^",
                    s=28,
                    color="#7f8c8d",
                    edgecolor="#2c3e50",
                    linewidth=0.4,
                    alpha=0.45,
                    transform=ccrs.PlateCarree(),
                    label=f"All {self.client_name} ({len(self.station_index)})",
                    zorder=4,
                )

        # Layer 5: Active Stations in Picker
        if active_stations:
            act_lons = [c[1] for c in active_stations.values()]
            act_lats = [c[0] for c in active_stations.values()]
            self.ax.scatter(
                act_lons,
                act_lats,
                marker="^",
                s=130,
                color="#e74c3c",
                edgecolor="black",
                linewidth=1.2,
                alpha=0.95,
                transform=ccrs.PlateCarree(),
                label=f"Active Stations ({len(active_stations)})",
                zorder=5,
            )

            if self.show_labels:
                for sta, (lat, lon, _) in active_stations.items():
                    self.ax.annotate(
                        sta,
                        xy=(lon, lat),
                        xytext=(6, 6),
                        textcoords="offset points",
                        fontsize=8.5,
                        fontweight="bold",
                        color="#1a252f",
                        transform=ccrs.PlateCarree(),
                        bbox=dict(
                            boxstyle="round,pad=0.2",
                            facecolor="white",
                            alpha=0.85,
                            edgecolor="#bdc3c7",
                            linewidth=0.5,
                        ),
                        zorder=6,
                    )

        # Layer 6: Earthquake Epicenter (if present / localized)
        status_event = "No Event Coordinates"
        if event_info:
            evla, evlo, depth_km, ot = event_info
            depth_str = f", Depth: {depth_km:.1f} km" if depth_km is not None else ""
            status_event = f"Epicenter: Lat {evla:.3f}°, Lon {evlo:.3f}°{depth_str}"

            # Epicenter Star
            self.ax.scatter(
                [evlo],
                [evla],
                marker="*",
                s=340,
                color="#f1c40f",
                edgecolor="#c0392b",
                linewidth=1.8,
                transform=ccrs.PlateCarree(),
                label="Hypocenter / Epicenter",
                zorder=7,
            )

            # Text annotation
            label_text = "★ Epicenter"
            if depth_km is not None:
                label_text += f"\nZ: {depth_km:.1f} km"
            self.ax.annotate(
                label_text,
                xy=(evlo, evla),
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=9,
                fontweight="bold",
                color="#962d00",
                transform=ccrs.PlateCarree(),
                bbox=dict(
                    boxstyle="round,pad=0.25",
                    facecolor="#fff9e6",
                    alpha=0.9,
                    edgecolor="#e67e22",
                    linewidth=0.8,
                ),
                zorder=8,
            )

            # Layer 7: Focal Mechanism Beachball (if computed)
            if self.focal_mechanism:
                try:
                    from obspy.imaging.beachball import beach
                    fm_data = self.focal_mechanism
                    if isinstance(fm_data, dict):
                        fm_sdr = (fm_data["strike"], fm_data["dip"], fm_data["rake"])
                    else:
                        fm_sdr = fm_data
                    
                    # Compute beachball size proportional to map extent
                    map_span = max(abs(extent[1] - extent[0]), abs(extent[3] - extent[2]))
                    bb_width = max(0.08 * map_span, 0.05)
                    bb = beach(
                        fm_sdr,
                        xy=(evlo, evla),
                        width=bb_width,
                        linewidth=1.2,
                        facecolor="#16a085",
                        edgecolor="#2c3e50",
                        zorder=9,
                    )
                    self.ax.add_collection(bb)
                except Exception as fm_err:
                    logger.warning(f"Failed to plot focal mechanism on map: {fm_err}")

        self.ax.legend(loc="upper right", framealpha=0.9, fontsize=8.5)
        try:
            self.canvas.draw()
        except Exception:
            try:
                self.canvas.draw_idle()
            except Exception:
                pass

        # Update status bar
        self.status_bar.showMessage(
            f"FDSN: {self.client_name} ({len(self.station_index)} stations) | "
            f"Active: {len(active_stations)} stations | {status_event}"
        )

    def closeEvent(self, event):
        try:
            plt.close(self.fig)
        except Exception:
            pass
        super().closeEvent(event)
