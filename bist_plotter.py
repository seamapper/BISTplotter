# -*- coding: utf-8 -*-
"""
Copyright (c) 2025, Center for Coastal and Ocean Mapping, University of New Hampshire
All rights reserved.

This file is part of BISTplotter and is licensed under the BSD 3-Clause License.
See LICENSE file in the project root for full license details.

Created on Sat Sep 15 13:30:15 2018
@author: kjerram and pjohnson   

Multibeam Echosounder Assessment Toolkit: Kongsberg BIST plotter

Read Kongsberg Built-In Self-Test (BIST) files for assessing
EM multibeam system performance and hardware health.

Note: this was developed primarily using EM302, EM710, and EM122 BIST files in SIS 4 format;
other formats and features will require additional work

N_RX_boards is typically 4; in some cases, this will be 2; this is currently set
manually, and will eventually be detected automatically.

EM2040 RX Noise BIST files may include columns corresponding to frequency, not RX board;
additional development is needed to handle this smoothly, especially between SIS 4 and SIS 5 formats.

Some factory limits for 'acceptable' BIST levels are parsed from the text file; limits for
RX impedance are not automatically detected; these can be found in the BIST text file and
manually adjusted in the plot_rx_z function in read_bist.py (or GUI as feature is added):

                # declare standard spec impedance limits
                RXrecmin = 600
                RXrecmax = 1000
                RXxdcrmin = 250
                RXxdcrmax = 1200

All impedance tests are meant as proxies for hardware health and not as replacement
for direct measurement with Kongsberg tools.

self.BIST_list = ["N/A or non-BIST", "TX Channels Z", "RX Channels Z", "RX Noise Level", "RX Noise Spectrum"]

- Test 1: TX Channels Impedance - plot impedance of TX channels at the transducer,
measured through the TRU with the TX Channels Impedance BIST. Input is a text file
saved from a telnet session running all TX Channels BISTs for the system (these
results are not saved to text file when running BISTs in the SIS interface).

- Test 1: RX Channels Impedance - plot impedance of RX channels measured at the
receiver (upper plot) and at the transducer (lower plot, measured through the receiver).
Input is a standard BIST text file saved from the Kongsberg SIS interface.

- Test 3: RX Noise - plot noise levels perceived by the RX system across all channels.
Input is a RX Noise BIST text file, ideally with multiple (10-20) BISTs saved to
one text file.  Each text file should correspond to the RX noise conditions of interest.
For instance, vessel-borne noise can be assessed across a range of speeds by running
10-20 BISTs at each speed, holding a constant heading at each, and logging one text
file per speed.  Individual tests may be compromised by transient noises, such as
swell hitting the hull; increasing test count will help to reduce the impact of
these events on the average noise plots.

- Test 4: RX Spectrum - similar to Test 3 (RX Noise) plotting, with RX Spectrum BIST
data collected at different speeds and headings

Additional development is pending to handle the various speed/heading options for
multiple RX Noise/Spectrum tests


"""
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtGui import QDoubleValidator, QPalette, QColor
from PyQt6.QtCore import Qt, QSize, QEvent, QTimer
import os
import sys
import datetime
# Add libs directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'libs'))
# import multibeam_tools.libs.readBIST
import read_bist
import numpy as np
import copy
import itertools
import re
import matplotlib
matplotlib.use('qtagg')  # Use qtagg backend for Qt6 compatibility
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import gridspec
from gui_widgets import *
from file_fun import remove_files
import json
from version import __version__


def apply_dark_theme(app):
    """Force the GUI to use a dark theme regardless of system/desktop theme."""
    # Use Fusion style for consistent cross-platform dark look
    app.setStyle('Fusion')
    
    # Build a dark palette
    dark = QColor(45, 45, 45)
    darker = QColor(35, 35, 35)
    mid = QColor(60, 60, 60)
    light = QColor(220, 220, 220)
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, dark)
    palette.setColor(QPalette.ColorRole.WindowText, light)
    palette.setColor(QPalette.ColorRole.Base, darker)
    palette.setColor(QPalette.ColorRole.AlternateBase, dark)
    palette.setColor(QPalette.ColorRole.Text, light)
    palette.setColor(QPalette.ColorRole.Button, dark)
    palette.setColor(QPalette.ColorRole.ButtonText, light)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.ToolTipBase, dark)
    palette.setColor(QPalette.ColorRole.ToolTipText, light)
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(140, 140, 140))
    
    app.setPalette(palette)
    
    # Optional: stylesheet for a few widgets that may not fully follow the palette
    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 1px solid #555555;
            border-radius: 4px;
            margin-top: 8px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }
        QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
            background-color: #2d2d2d;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 2px;
        }
        QListWidget {
            background-color: #2d2d2d;
            border: 1px solid #555555;
        }
        QScrollBar:vertical {
            background: #2d2d2d;
            width: 12px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical {
            background: #555555;
            border-radius: 6px;
            min-height: 20px;
        }
    """)


def load_bist_session_config():
    """Load BIST plotter session configuration including last used directories"""
    config_file = os.path.join(os.path.expanduser("~"), ".bist_plotter_session.json")
    
    # Use USERPROFILE on Windows, HOME on Unix-like systems
    default_dir = os.getenv('USERPROFILE') or os.getenv('HOME') or os.getcwd()
    default_config = {
        "last_input_directory": default_dir,
        "last_output_directory": default_dir
    }
    
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Update with any missing keys from default
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            return default_config
    except Exception as e:
        print(f"Warning: Could not load BIST session config: {e}")
        return default_config

def save_bist_session_config(config):
    """Save BIST plotter session configuration including last used directories"""
    config_file = os.path.join(os.path.expanduser("~"), ".bist_plotter_session.json")
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save BIST session config: {e}")

def update_bist_last_directory(config_key, directory):
    """Update the last used directory for a specific file type in BIST plotter"""
    if directory and os.path.exists(directory):
        config = load_bist_session_config()
        config[config_key] = directory
        save_bist_session_config(config)

def clear_bist_session_config():
    """Clear the BIST plotter session configuration"""
    config_file = os.path.join(os.path.expanduser("~"), ".bist_plotter_session.json")
    try:
        if os.path.exists(config_file):
            os.remove(config_file)
            print("BIST session configuration cleared.")
    except Exception as e:
        print(f"Warning: Could not clear BIST session config: {e}")


class MainWindow(QtWidgets.QMainWindow):
    media_path = os.path.join(os.path.dirname(__file__), "media")

    def __init__(self, parent=None):
        super(MainWindow, self).__init__()

        # set up main window
        self.mainWidget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.mainWidget)
        # Default size matches the former fixed layout; user may resize.
        # Exports regenerate figures via save_figs=True and are unaffected by window size.
        self.resize(1600, 1000)
        self.setMinimumSize(1100, 700)
        self.setWindowTitle(
            'UNH/CCOM-JHC BIST Plotter v.%s - kjerram@ccom.unh.edu & pjohnson@ccom.unh.edu' % __version__
        )
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.media_path, "mac.ico")))

        if os.name == 'nt':  # necessary to explicitly set taskbar icon
            import ctypes
            current_app_id = 'MAC.BISTPlotter.' + __version__  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(current_app_id)

        # initialize other necessities
        self.filenames = ['']
        self.input_dir = ''
        
        # Load last output directory from session config
        config = load_bist_session_config()
        self.output_dir = config.get("last_output_directory", os.getcwd())
        
        self.missing_fields = []
        self.conflicting_fields = []
        self._title_chk_user = set()
        self.model_updated = False
        self.sn_updated = False
        self.date_updated = False
        self.warn_user = True
        self.param_list = []

        self.noise_params = {'SOG (kt)': '_08_kts',
                             'STW (kt)': '_08_kts',
                             'RPM': '_100RPM',
                             'Handle (%)': '_50_pct',
                             'Pitch (%)': '_50_pct',
                             'Pitch (deg)': '_30_deg',
                             'Azimuth (deg)': '_045T_270S'}

        self.default_prm_str = '_08_kts'
        self.prm_unit_cbox_last_index = 0
        self.prm_str_tb_last_text = '_08_kts'
        self.gb_toggle = True
        self.file_into_seas_str = '(INTO SEAS)'
        self.swell_dir_updated = False
        self.swell_dir_default = '999'
        self.swell_dir_message = True
        self.current_default = '0'
        self._ignore_sis5_user_disabled_on_sog = False
        self._ignore_sis5_syncing = False
        self._transient_filter_syncing = False
        self._transient_filter_applied = None
        self._active_transient_threshold = None
        self._sn_user_entered = False
        self._model_user_entered = False
        self._date_user_entered = False
        self._freq_user_entered = False
        self._sn_autofill_text = '999'
        self._date_autofill_text = 'yyyy/mm/dd'
        self._freq_autofill_text = '?'
        self._sysinfo_programmatic_update = False
        self._sysinfo_replot_active = False
        self._sn_programmatic_update = False
        self._noise_plot_styles = [
            'vs. Speed', 'vs. Speed (Binned) - 1kt', 'vs. Speed (Binned) - 2kt',
            'vs. RPM', 'vs. RPM (Binned)', 'vs. Pitch (deg)', 'vs. Pitch (Binned) - deg',
            'vs. Pitch (%)', 'vs. Pitch (Binned) - %', 'vs. Azimuth']
        self._channel_plot_styles = ['Plot All', 'History']
        self._saved_noise_plot_style = self._noise_plot_styles[0]
        self._saved_channel_plot_style = 'Plot All'
        self.last_channel_plot_style = 'Plot All'

        # Navigation controls for multiple charts
        self.all_figures = []  # Store all frequency plots
        self.frequency_data = []  # Store data needed to regenerate plots
        self.current_chart_index = 0
        self.total_charts = 0
        self.freq_list = []  # Store chart names

        # list of available test types; RX Noise is only available vs. speed, not heading at present
        # RX Noise Spectrum is not available yet; update accordingly
        self.bist_list = ["N/A or non-BIST", "TX Channels Z", "RX Channels Z", "RX Noise Level", "RX Noise Spectrum"]

        # set up layouts of main window
        self.set_left_layout()
        self.set_right_layout()
        self.set_main_layout()

        # enable initial tab/input states and custom speed list
        self.update_buttons()
        self.update_param_info()
        
        # Note: Session data is now loaded only when user clicks "Load Session" button

        # set up file control actions
        self.add_file_btn.clicked.connect(lambda: self.add_files('Kongsberg BIST .txt(*.txt)'))
        self.get_indir_btn.clicked.connect(self.get_input_dir)
        self.export_plots_btn.clicked.connect(self.export_plots)
        self.export_analysis_btn.clicked.connect(self.export_analysis)
        self.import_analysis_btn.clicked.connect(self.import_analysis)
        self.rmv_file_btn.clicked.connect(self.remove_bist_files)
        self.clr_file_btn.clicked.connect(lambda: self.remove_bist_files(clear_all=True))
        self.show_path_chk.stateChanged.connect(self.show_file_paths)

        # set up BIST selection and plotting actions
        self.select_type_btn.clicked.connect(self.select_bist)
        self.clear_type_btn.clicked.connect(self.clear_bist)
        # self.verify_bist_btn.clicked.connect(self.verify_system_info)
        self.plot_bist_btn.clicked.connect(self.plot_bist)
        self.transient_filter_chk.stateChanged.connect(self._on_transient_filter_changed)
        self.transient_db_tb.editingFinished.connect(self._on_transient_filter_changed)
        self.remove_nulls_chk.stateChanged.connect(self._on_remove_nulls_changed)
        # self.custom_info_chk.stateChanged(self.custom_info_gb.setEnabled(self.custom_info_chk.isChecked()))

        # System info: commit on Enter (text) or dropdown selection (model); then refresh plots
        self.model_cbox.activated.connect(self.on_system_info_committed)
        self.sn_tb.returnPressed.connect(self.on_system_info_committed)
        self.sn_tb.editingFinished.connect(self._on_sn_user_edited)
        self.ship_tb.returnPressed.connect(self.on_system_info_committed)
        self.cruise_tb.returnPressed.connect(self.on_system_info_committed)
        for optional_field in (self.ship_tb, self.cruise_tb):
            optional_field.textChanged.connect(
                lambda _text, field=optional_field: self._refresh_optional_sysinfo_style(field))
            optional_field.editingFinished.connect(
                lambda field=optional_field: self._on_optional_sysinfo_edited(field))
            optional_field.installEventFilter(self)
            self._set_optional_sysinfo_undefined(optional_field)
        self.date_tb.returnPressed.connect(self.on_system_info_committed)
        self.date_tb.editingFinished.connect(self._on_date_user_edited)
        self.freq_tb.returnPressed.connect(self.on_system_info_committed)
        self.freq_tb.editingFinished.connect(self._on_freq_user_edited)
        for field, title_chk in self._title_checkboxes().items():
            title_chk.stateChanged.connect(
                lambda _state, name=field: self._on_title_checkbox_toggled(name))
        self.warn_user_chk.stateChanged.connect(self.verify_system_info)

        self.type_cbox.activated.connect(self.update_buttons)
        self.type_cbox.activated.connect(self.auto_plot_bist_type)
        self.type_cbox.currentTextChanged.connect(self.update_buttons)  # Also handle text changes
        self.noise_test_type_cbox.activated.connect(self.update_buttons)
        self.noise_test_type_cbox.currentTextChanged.connect(self.auto_plot_noise_type)
        # self.prm_unit_cbox.activated.connect(self.update_buttons)
        self.prm_unit_cbox.activated.connect(self.update_noise_param_unit)
        self.prm_unit_cbox.currentTextChanged.connect(self.update_noise_param_unit)
        self.ignore_sis5_speeds_chk.stateChanged.connect(self._on_ignore_sis5_user_toggle)
        self.prm_str_tb.textChanged.connect(self.update_noise_param_string)
        
        # Connect RX Noise Testing controls for auto-update
        self.binned_calculated_mean_cb.currentTextChanged.connect(self._on_calculated_mean_changed)
        self.binned_calculated_mean_gb.toggled.connect(self.auto_update_plot)
        self.binned_error_type_cb.currentTextChanged.connect(self.auto_update_plot)
        self.binned_individual_cb.currentTextChanged.connect(self.auto_update_plot)
        
        # Connect RX Noise Testing parameter controls for auto-update
        self.prm_plot_min_tb.returnPressed.connect(self.trigger_auto_update)
        self.prm_plot_max_tb.returnPressed.connect(self.trigger_auto_update)
        self.current_tb.returnPressed.connect(self.trigger_auto_update)
        self.current_dir_cbox.currentTextChanged.connect(self.auto_update_plot)
        self.sort_cbox.currentTextChanged.connect(self.auto_update_plot)
        
        # Connect binned RX noise Y-axis range controls for auto-update
        self.binned_rxnoise_min_tb.returnPressed.connect(self.trigger_auto_update)
        self.binned_rxnoise_max_tb.returnPressed.connect(self.trigger_auto_update)
        self.binned_rxnoise_range_gb.toggled.connect(self.auto_update_plot)
    
    def get_resource_path(self, relative_path):
        """Get the absolute path to a resource file, works both in development and PyInstaller bundle"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
            # In PyInstaller, the media folder is in sys._MEIPASS, so use relative_path directly
            full_path = os.path.join(base_path, relative_path)
        except Exception:
            # If not running in PyInstaller bundle, use the media_path directly
            # The media folder is at the project root (same level as the script)
            base_path = self.media_path
            # If relative_path already includes "media/", extract just the filename
            # Otherwise, construct the full path
            if relative_path.startswith("media/"):
                filename = os.path.basename(relative_path)
                full_path = os.path.join(base_path, filename)
            else:
                full_path = os.path.join(base_path, relative_path)
        
        # Debug: Print the paths being checked
        print(f"Debug: Checking path: {full_path}")
        
        return full_path

    @staticmethod
    def _program_freeze_date_text():
        """Return freeze/build date for the About view (exe mtime when frozen)."""
        if getattr(sys, 'frozen', False):
            try:
                ts = os.path.getmtime(sys.executable)
                return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
            except OSError:
                return 'Unknown'
        return 'Not frozen (running from source)'

    def _resolve_media_file(self, filename):
        """Resolve a media asset for source runs and PyInstaller bundles."""
        candidates = [
            os.path.join(self.media_path, filename),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media', filename),
        ]
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.insert(0, os.path.join(meipass, 'media', filename))
        for path in candidates:
            if path and os.path.isfile(path):
                return path
        return candidates[0]

    def _build_about_program_widget(self):
        """Build the About This Program content shown in the Plot Window on startup."""
        tab = QtWidgets.QWidget()
        tab.setSizePolicy(QtWidgets.QSizePolicy.Policy.MinimumExpanding,
                          QtWidgets.QSizePolicy.Policy.MinimumExpanding)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = self._resolve_media_file('mac.png')
        pixmap = QtGui.QPixmap(logo_path)
        if not pixmap.isNull():
            max_w = 280
            if pixmap.width() > max_w:
                pixmap = pixmap.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        else:
            logo_label.setText('MAC')
            logo_label.setStyleSheet('font-size: 28px; font-weight: bold;')
        layout.addWidget(logo_label)

        title = QtWidgets.QLabel('BIST Plotter')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size: 22px; font-weight: bold; margin-top: 8px;')
        layout.addWidget(title)

        version = QtWidgets.QLabel(f'Version {__version__}')
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet('font-size: 14px;')
        layout.addWidget(version)

        freeze = QtWidgets.QLabel(f'Frozen: {self._program_freeze_date_text()}')
        freeze.setAlignment(Qt.AlignmentFlag.AlignCenter)
        freeze.setStyleSheet('font-size: 13px; color: #bbbbbb;')
        layout.addWidget(freeze)

        developers = QtWidgets.QLabel(
            'Developers: Kevin Jerram (kjerram@ccom.unh.edu) and '
            'Paul Johnson (pjohnson@ccom.unh.edu)'
        )
        developers.setAlignment(Qt.AlignmentFlag.AlignCenter)
        developers.setWordWrap(True)
        developers.setStyleSheet('font-size: 13px; margin-top: 4px;')
        layout.addWidget(developers)

        body = QtWidgets.QLabel()
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setOpenExternalLinks(True)
        body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.setStyleSheet('font-size: 13px; line-height: 1.4; margin-top: 16px;')
        body.setText(
            '<p>Multibeam Echosounder Assessment Toolkit: Kongsberg BIST Plotter.</p>'
            '<p>Read Kongsberg Built-In Self-Test (BIST) files for assessing EM multibeam '
            'system performance and hardware health, including TX/RX channel impedance, '
            'RX noise level, and related test products.</p>'
            '<p>Load one or more BIST text files, choose a test type, then use '
            '<b>Plot BIST</b> to display results in this window. Use the navigation '
            'controls below when multiple charts are available.</p>'
            '<p>Developed at the Center for Coastal and Ocean Mapping (CCOM) / '
            'Joint Hydrographic Center (JHC), University of New Hampshire.</p>'
            '<p>This work was supported by the National Science Foundation under:</p>'
            '<ul>'
            '<li>Award #1933720 — <i>Collaborative Research: Optimization of the Multibeam '
            'Sonar Systems of the U.S. Academic Fleet through Coordinated System Testing, '
            'Tool Development, and Community Outreach</i></li>'
            '<li>Award #2614984 — <i>Advancing U.S. Leadership in Seafloor Mapping Technology '
            'for the Academic Research Fleet</i></li>'
            '</ul>'
        )
        layout.addWidget(body)
        layout.addStretch(1)

        scroll.setWidget(content)
        tab_layout = QtWidgets.QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    def _show_about_in_plot_window(self):
        """Show the About view in the Plot Window."""
        if hasattr(self, 'plot_stack') and hasattr(self, 'about_plot_widget'):
            self.plot_stack.setCurrentWidget(self.about_plot_widget)

    def _show_plot_canvas(self):
        """Show the matplotlib canvas in the Plot Window (hides About)."""
        if hasattr(self, 'plot_stack') and hasattr(self, 'plot_figure_canvas'):
            self.plot_stack.setCurrentWidget(self.plot_figure_canvas)

    def set_right_layout(self):
        # set layout with file controls on right, sources on left, and progress log on bottom
        btnh = 20  # height of file control button
        btnw = 110  # width of file control button

        # set the custom info control buttons
        self.sys_info_lbl = QtWidgets.QLabel('Default: any info in BIST will be used;'
                                             '\nmissing fields require user input')

        self.warn_user_chk = CheckBox('Check for missing or conflicting info',
                                      True, 'warn_user_chk',
                                      'Turn off warnings only if you are certain the system info is consistent')

        self.sys_info_lbl.setStyleSheet('font: 8pt')
        title_tip = ('Include this value in plot titles. Turned off when loaded files '
                     'leave it unknown or conflicting, until you check it or edit the value.')
        self.model_title_chk = CheckBox('Model:', True, 'model_title_chk', title_tip, 100, 20)
        self.model_cbox = ComboBox(['EM 2040', 'EM 2042', 'EM 302', 'EM 304', 'EM 710', 'EM 712', 'EM 122', 'EM 124'],
                                   200, 20, 'model', 'Select the EM model')
        self.model_cbox.setStyleSheet("color: white;")
        model_info_layout = BoxLayout([self.model_title_chk, self.model_cbox], 'h')

        self.sn_title_chk = CheckBox('Serial No.:', True, 'sn_title_chk', title_tip, 100, 20)
        self.sn_tb = LineEdit('999', 200, 20, 'sn', 'Enter the serial number')
        sn_info_layout = BoxLayout([self.sn_title_chk, self.sn_tb], 'h')

        self.freq_title_chk = CheckBox('Frequency:', False, 'freq_title_chk', title_tip, 100, 20)
        self.freq_tb = LineEdit('?', 200, 20, 'frequency',
                                'Nominal frequency from the model. Edit this to replace the frequency in plot titles.')
        self.freq_tb.setStyleSheet('color: white;')
        freq_info_layout = BoxLayout([self.freq_title_chk, self.freq_tb], 'h')

        self.ship_title_chk = CheckBox('Ship Name:', False, 'ship_title_chk', title_tip, 100, 20)
        self.ship_tb = LineEdit('?', 200, 20, 'ship', 'Enter the ship name (optional). A magenta ? means it is not set and will be left out of plot titles.')
        ship_info_layout = BoxLayout([self.ship_title_chk, self.ship_tb], 'h')

        self.cruise_title_chk = CheckBox('Description:', False, 'cruise_title_chk', title_tip, 100, 20)
        self.cruise_tb = LineEdit('?', 200, 20, 'cruise_name', 'Enter the description (optional). A magenta ? means it is not set and will be left out of plot titles.')
        cruise_info_layout = BoxLayout([self.cruise_title_chk, self.cruise_tb], 'h')

        self.date_title_chk = CheckBox('Date:', True, 'date_title_chk', title_tip, 100, 20)
        self.date_tb = LineEdit('yyyy/mm/dd', 200, 20, 'date', 'Enter the date (BISTs over multiple days will '
                                                              'use dates in files, if available)')
        self.date_tb.setStyleSheet("color: white;")
        date_info_layout = BoxLayout([self.date_title_chk, self.date_tb], 'h')

        # set the custom info button layout
        custom_info_layout = BoxLayout([self.sys_info_lbl, model_info_layout, sn_info_layout, freq_info_layout,
                                        ship_info_layout, cruise_info_layout, date_info_layout, self.warn_user_chk], 'v')

        # set the custom info groupbox
        self.custom_info_gb = QtWidgets.QGroupBox('System Information')
        self.custom_info_gb.setLayout(custom_info_layout)
        self.custom_info_gb.setFixedWidth(320)  # Increased width to accommodate wider input boxes

        # add file control buttons and file list
        self.add_file_btn = PushButton('Add Files', btnw, btnh, 'add_files', 'Add BIST .txt files')
        self.get_indir_btn = PushButton('Add Directory', btnw, btnh, 'add_dir',
                                        'Add a directory with BIST .txt files')
        self.include_subdir_chk = CheckBox('Include subdirectories', True, 'include_subdir_chk',
                                           'Include subdirectories when adding a directory')
        self.rmv_file_btn = PushButton('Remove Selected', btnw, btnh, 'rmv_files', 'Remove selected files')
        self.clr_file_btn = PushButton('Remove All Files', btnw, btnh, 'clr_file_btn', 'Remove all files')
        self.show_path_chk = CheckBox('Show file paths', False, 'show_paths_chk', 'Show paths in file list')
        self.export_plots_btn = PushButton('Export Plots', btnw, btnh, 'export_plots_btn',
                                           'Save plot PNG files and out-of-spec reports from the last plot run')
        self.export_plots_btn.setEnabled(False)
        self.import_analysis_btn = PushButton('Import Analysis', btnw, btnh, 'import_analysis_btn',
                                              'Load an analysis JSON file, restore its settings, and recreate the plots')
        self.export_analysis_btn = PushButton('Export Analysis', btnw, btnh, 'export_analysis_btn',
                                              'Save the plots and an analysis JSON file that can recreate them')
        self.export_analysis_btn.setEnabled(False)
        self._export_btn_style_default = ''
        self._export_btn_style_pending = (
            'QPushButton { color: #FF8C00; font-weight: bold; }'
        )
        self._export_pending = False
        self._startup_action_pending = True
        self.add_file_btn.setStyleSheet(self._export_btn_style_pending)
        self.get_indir_btn.setStyleSheet(self._export_btn_style_pending)
        self.import_analysis_btn.setStyleSheet(self._export_btn_style_pending)
        self.last_plotted_bist = None
        self.last_bist_test_type = None
        self.last_plotted_files = []
        self.last_into_seas_file = None

        # Create horizontal layout for Add Files and Add Directory buttons
        add_files_dir_layout = BoxLayout([self.add_file_btn, self.get_indir_btn], 'h', equal_width=True)
        
        # Create horizontal layout for Remove Selected and Remove All Files buttons
        remove_files_layout = BoxLayout([self.rmv_file_btn, self.clr_file_btn], 'h', equal_width=True)
        
        # Checkboxes keep natural size; equal_width is for push buttons only
        checkboxes_layout = BoxLayout([self.include_subdir_chk, self.show_path_chk], 'h')
        
        # set the file control button layout (placed under file list in Sources groupbox)
        self.file_btn_layout = BoxLayout([add_files_dir_layout,
                                          remove_files_layout, checkboxes_layout], 'v')

        # set the BIST selection buttons
        lblw = 60
        lblh = 20
        type_cbox_lbl = Label('Select BIST:', lblw, lblh, 'type_cbox_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        type_cbox_lbl.setFixedWidth(lblw)
        self.type_cbox = ComboBox(self.bist_list[1:-1], 100, btnh, 'bist_cbox',
                                  'Select a BIST type for file verification and plotting')
        self.type_cbox.setCurrentIndex(2)  # Set "RX Noise Level" as default (index 2 in the combo box)
        bist_type_layout = BoxLayout([type_cbox_lbl, self.type_cbox], 'h', add_stretch=True)

        noise_test_type_lbl = Label('Plot Style:', 78, lblh, 'noise_type_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        noise_test_type_lbl.setFixedWidth(78)
        self.noise_test_type_cbox = ComboBox(self._noise_plot_styles, 200, btnh, 'noise_test_cbox',
                                             'Choose what to plot for the selected BIST type.\n'
                                             'RX Noise: noise mode (speed, RPM, pitch, azimuth).\n'
                                             'TX or RX Channels: Plot All, or History only.')
        self.noise_test_type_cbox.setEnabled(True)
        noise_type_layout = BoxLayout([noise_test_type_lbl, self.noise_test_type_cbox], 'h', add_stretch=True)

        cmap_lbl = Label('Colormap:', lblw, lblh, 'cmap_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        cmap_lbl.setFixedWidth(lblw)
        self.cmap_cbox = ComboBox(['Jet', 'Inferno', 'Hot', 'RedBlue', 'CoolWarm', 'Reversed Managua'], 70, btnh, 'cmap_cbox', 'Select desired colormap')
        self.redblue_center_spin = QtWidgets.QDoubleSpinBox()
        self.redblue_center_spin.setRange(30, 70)
        self.redblue_center_spin.setValue(55)
        self.redblue_center_spin.setDecimals(1)
        self.redblue_center_spin.setFixedWidth(55)
        self.redblue_center_spin.setToolTip('Center (dB): inflection point for RedBlue, CoolWarm, and Reversed Managua')
        redblue_lbl = Label('Center:', 38, lblh, 'redblue_center_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        def _show_center(t):
            self.redblue_center_spin.setVisible(t in ('RedBlue', 'CoolWarm', 'Reversed Managua'))
        self.redblue_center_spin.setVisible(self.cmap_cbox.currentText() in ('RedBlue', 'CoolWarm', 'Reversed Managua'))
        self.cmap_cbox.currentTextChanged.connect(_show_center)
        self.cmap_cbox.currentTextChanged.connect(self._on_colormap_changed)
        cmap_layout = BoxLayout([cmap_lbl, self.cmap_cbox, redblue_lbl, self.redblue_center_spin], 'h', add_stretch=True)

        self.select_type_btn = PushButton('Select BISTs', btnw, btnh, 'select_type',
                                          'Filter and select source files by the chosen BIST type')
        self.clear_type_btn = PushButton('Clear Selected', btnw, btnh, 'clear_type', 'Clear file selection')
        self.plot_bist_btn = PushButton('Plot Selected', btnw, btnh, 'plot_bist',
                                        'Plot selected, verified files (using current system information above, '
                                        'if not available in BIST)')

        # Create horizontal layout for Select BISTs and Clear Selected buttons
        select_clear_layout = BoxLayout([self.select_type_btn, self.clear_type_btn], 'h', equal_width=True)
        
        plot_btn_layout = BoxLayout([self.plot_bist_btn, self.export_plots_btn], 'h', equal_width=True)
        analysis_btn_layout = BoxLayout([self.import_analysis_btn, self.export_analysis_btn], 'h', equal_width=True)

        # set the BIST options layout
        bist_options_layout = BoxLayout([bist_type_layout, noise_type_layout, cmap_layout,
                                        select_clear_layout, plot_btn_layout, analysis_btn_layout], 'v')

        # set RX noise test parameters
        prm_unit_lbl = Label('Test units:', 110, 20, 'prm_unit_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        # self.prm_unit_cbox = ComboBox(['SOG (kts)', 'RPM', 'Handle (%)', 'Pitch (%)', 'Pitch (deg)', 'Azimuth (deg)'],
        #                               90, 20, 'prm_unit_cbox', 'Select the test units')
        self.prm_unit_cbox = ComboBox([prm for prm in self.noise_params.keys()],
                                      90, 20, 'prm_unit_cbox', 'Select the test units\n\n'
                                                               'SOG: Speed Over Ground\n'
                                                               'STW: Speed Through Water\n'
                                                               'RPM: Rotations Per Minute\n')
        prm_unit_layout = BoxLayout([prm_unit_lbl, self.prm_unit_cbox], 'h', full_width=True)
        # self.prm_unit_gb = GroupBox('Noise testing', prm_unit_layout, False, False, 'prm_unit_gb')

        # set parameter plot limits
        self.prm_plot_min_tb = LineEdit('0', 40, 20, 'prm_plot_min_tb', 'Enter the parameter plot Y-axis minimum')
        self.prm_plot_max_tb = LineEdit('10', 40, 20, 'prm_plot_max_tb', 'Enter the parameter plot Y-axis maximum')
        prm_plot_min_lbl = Label('Min:', 20, 20, 'prm_plot_min_lbl', (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        prm_plot_max_lbl = Label('Max:', 20, 20, 'prm_plot_max_lbl', (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        prm_plot_lim_layout = BoxLayout([prm_plot_min_lbl, self.prm_plot_min_tb,
                                         prm_plot_max_lbl, self.prm_plot_max_tb], 'h', full_width=True)

        self.prm_plot_lim_gb = GroupBox('Set X-axis Limits', prm_plot_lim_layout,
                                        True, False, 'parse_test_params_gb')

        self.prm_plot_lim_gb.setToolTip('Set the minimum and maximum parameters for plotting\n\n'
                                        'This creates consistent axes for test params aross data sets with '
                                        'different min/max values (e.g., speeds going into seas vs. with seas')

        # RX noise range: binned Y-axis and heatmap color ramp
        self.binned_rxnoise_min_tb = LineEdit('30', 40, 20, 'binned_rxnoise_min_tb', 'Minimum RX noise (dB)')
        self.binned_rxnoise_max_tb = LineEdit('70', 40, 20, 'binned_rxnoise_max_tb', 'Maximum RX noise (dB)')
        binned_rxnoise_min_lbl = Label('Min:', 20, 20, 'binned_rxnoise_min_lbl', (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        binned_rxnoise_max_lbl = Label('Max:', 20, 20, 'binned_rxnoise_max_lbl', (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        binned_rxnoise_range_layout = BoxLayout([binned_rxnoise_min_lbl, self.binned_rxnoise_min_tb,
                                                 binned_rxnoise_max_lbl, self.binned_rxnoise_max_tb], 'h',
                                                full_width=True)
        
        # Create group box for binned RX noise range controls (checkable)
        binned_rxnoise_range_gb_layout = BoxLayout([binned_rxnoise_range_layout], 'v', full_width=True)
        self.binned_rxnoise_range_gb = GroupBox('RX noise range (db)', binned_rxnoise_range_gb_layout, 
                                                True, True, 'binned_rxnoise_range_gb')
        self.binned_rxnoise_range_gb.setToolTip('RX noise range in dB (default 30-70 dB). Sets the Y-axis on binned plots and the color ramp on RX noise heatmaps.\n'
                                                'Values below Min are black and values above Max are magenta.\n'
                                                'When unchecked, the axis and color range follow the plotted data.')
        
        # Initially enable the Min/Max text boxes since group box is checked by default
        self.binned_rxnoise_min_tb.setEnabled(True)
        self.binned_rxnoise_max_tb.setEnabled(True)

        # set binned calculated-mean controls
        binned_calculated_mean_lbl = Label('Mean:', 50, 20, 'binned_calculated_mean_lbl',
                                           (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        self.binned_calculated_mean_cb = ComboBox(
            ['Arithmetic & Linear Mean', 'Arithmetic Mean', 'Linear Mean'],
            210, 20, 'binned_calculated_mean_cb',
            'Arithmetic mean averages the dB values. Linear mean averages in linear units, then converts back to dB.')
        binned_calculated_mean_layout = BoxLayout(
            [binned_calculated_mean_lbl, self.binned_calculated_mean_cb], 'h', full_width=True)
        binned_calculated_mean_gb_layout = BoxLayout([binned_calculated_mean_layout], 'v', full_width=True)
        self.binned_calculated_mean_gb = GroupBox(
            'Binned calculated mean', binned_calculated_mean_gb_layout,
            True, True, 'binned_calculated_mean_gb')
        self.binned_calculated_mean_gb.setToolTip(
            'Choose which calculated means are drawn on binned RX noise plots')

        # set binned RX noise error bar type controls
        binned_error_type_lbl = Label('Error bar type:', 80, 20, 'binned_error_type_lbl', (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        self.binned_error_type_cb = ComboBox(
            ['Standard Deviation Linear', 'Standard Error Linear',
             'Standard Deviation Arithmetic', 'Standard Error Arithmetic'],
            210, 20, 'binned_error_type_cb',
            'Linear bars are the spread of the linear mean. Arithmetic bars are the spread of the dB values around the arithmetic mean. Standard error divides that spread by the square root of the number of tests.')
        self.binned_error_type_cb.setCurrentIndex(0)
        binned_error_type_layout = BoxLayout([binned_error_type_lbl, self.binned_error_type_cb], 'h',
                                             full_width=True)
        
        # Create group box for binned error bar type controls
        binned_error_type_gb_layout = BoxLayout([binned_error_type_layout], 'v', full_width=True)
        self.binned_error_type_gb = GroupBox('Binned plot error bars', binned_error_type_gb_layout, 
                                            True, True, 'binned_error_type_gb')
        self.binned_error_type_gb.setToolTip('Choose standard deviation or standard error for the linear mean or the arithmetic mean on binned RX noise plots')

        # set binned individual measurements display controls
        binned_individual_lbl = Label('Individual points:', 100, 20, 'binned_individual_lbl', (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        self.binned_individual_cb = ComboBox(['Binned (Cyan)', 'Non-binned (Light Grey)', 'Both (Binned + Non-binned)'], 150, 20, 'binned_individual_cb')
        self.binned_individual_cb.setCurrentIndex(1)  # Set default to "Non-binned (Light Grey)"
        self.binned_individual_cb.setToolTip('Choose between binned individual measurements (cyan), non-binned individual measurements (light grey), or both layered together')
        binned_individual_layout = BoxLayout([binned_individual_lbl, self.binned_individual_cb], 'h',
                                             full_width=True)
        
        # Create group box for binned individual measurements controls
        binned_individual_gb_layout = BoxLayout([binned_individual_layout], 'v', full_width=True)
        self.binned_individual_gb = GroupBox('Individual measurements display', binned_individual_gb_layout, 
                                            True, True, 'binned_individual_gb')
        self.binned_individual_gb.setToolTip('Control the display of individual measurements on 1kt and 2kt binned RX noise plots')

        # set options for getting RX Noise vs speed string from filename, custom speed vector, and/or sorting
        # prm_str_tb_lbl = Label('Filename speed string:', 120, 20, 'prm_str_tb_lbl', (Qt.AlignRight | Qt.AlignVCenter))
        prm_str_tb_lbl = Label('Filename string:', 120, 20, 'prm_str_tb_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        self.prm_str_tb = LineEdit(self.default_prm_str, 65, 20, 'prm_str_tb',
                                   'Enter an example string for the test parameter recorded in the filename (e.g., '
                                   '"_08_kts", "_045_deg", "_pitch_30_pct") for each BIST text file. This string is '
                                   'used only to search for the format of the test parameter in the filename.\n\n'
                                   'Note that heading/azimuth tests require specific formatting for the heading and '
                                   'swell direction (follow direction in log and/or pop-up message).'
                                   '\n\nThe user will be warned if the test parameter cannot be parsed for all files. '
                                   'Using a consistent filename format will help greatly.'
                                   '\n\nNotes for speed testing:'
                                   '\n\nSIS 4 RX Noise BISTs do not include speed, so the user must note the test speed '
                                   'in the text filename, e.g., default naming of "BIST_FILE_NAME_02_kt.txt" or '
                                   '"_120_RPM.txt", etc. '
                                   '\n\nSIS 5 BISTs include speed over ground, which is parsed and used by default, '
                                   'if available. The user may assign a custom speed list in any case if speed is not '
                                   'available in the filename or applicable for the desired plot.')
        prm_str_layout = BoxLayout([prm_str_tb_lbl, self.prm_str_tb], 'h', full_width=True)

        # set current text input for converting SOG to STW
        self.current_tb = LineEdit(self.current_default, 15, 20, 'current_tb',
                                     'Enter the apparent current magnitude (kt, along the ship heading) and '
                                     'select the direction (with or against the ship) during testing\n\n'
                                     'This will be used to convert speed over ground (SOG, parsed from file or file '
                                     'name) to speed through water (STW) for plotting\n\n'
                                     'NOTE: Tests collected with and against the current should be plotted separately')
        self.current_tb.setEnabled(False)
        current_lbl = Label('Current (kt):', 20, 20, 'current_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        self.current_dir_cbox = ComboBox(['with ship', 'against ship'], 80, 20, 'current_dir_cbox',
                                         'Select the direction of the apparent current\n\n'
                                         '"With ship" means the ship is being aided by the current (SOG > STW)\n'
                                         '"Against ship" means the ship is fighting the current (SOG < STW)')
        self.current_dir_cbox.setEnabled(False)
        current_layout = BoxLayout([current_lbl, self.current_tb, self.current_dir_cbox], 'h', full_width=True)

        # set swell direction text input
        self.swell_dir_tb = LineEdit(self.swell_dir_default, 40, 20, 'swell_dir_tb',
                                     'Enter the swell direction (degrees, compass direction from which the prevailing seas are '
                                     'coming)\n\n'
                                     'For instance, swell coming from the northeast would be entered as 45 deg')
        self.swell_dir_tb.setEnabled(False)

        swell_dir_lbl = Label('Swell direction (deg):', 120, 20, 'swell_dir_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        swell_dir_layout = BoxLayout([swell_dir_lbl, self.swell_dir_tb], 'h', full_width=True)

        sort_order_lbl = Label('Sort order:', 120, 20, 'sort_order_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        # self.sort_cbox = ComboBox(['Ascending', 'Descending', 'Unsorted'], 80, 20, 'sort_cbox',
        #                           'Select the test parameter sort order for plotting ("Unsorted" will plot tests '
        #                           'in the order they were parsed)')
        self.sort_cbox = ComboBox(['Ascending', 'Descending', 'Unsorted', 'Reverse'], 80, 20, 'sort_cbox',
                                  'Select the test parameter sort order for plotting ("Unsorted" will plot tests '
                                  'in the order they were parsed)')
        self.ignore_sis5_speeds_chk = CheckBox('Ignore SiS5 Speeds', False, 'ignore_sis5_speeds_chk',
                                               'Ignore speed parsed from SiS5 file contents and parse speed from '
                                               'filename using the Filename string format')
        sort_order_layout = BoxLayout([sort_order_lbl, self.sort_cbox, self.ignore_sis5_speeds_chk], 'h',
                                      full_width=True)

        default_test_params_layout = BoxLayout([prm_str_layout], 'v', full_width=True)

        self.parse_test_params_gb = GroupBox('Parse test params from files', default_test_params_layout,
                                               True, True, 'parse_test_params_gb')

        plotting_test_params_layout = BoxLayout([current_layout, swell_dir_layout, sort_order_layout],
                                                'v', full_width=True)
        self.plotting_test_params_gb = GroupBox('Plotting && Test Params', plotting_test_params_layout,
                                                False, False, 'plotting_test_params_gb')

        self.parse_test_params_gb.setToolTip('The RX Noise test params (e.g., speed) will be parsed from the file, '
                                             'if available (e.g., speed in SIS 5 format).\n\n'
                                             'If not found in the file, the parser will search for speed or heading '
                                             'information in the file name using the provided test string format '
                                             '(e.g., "_08_kts.txt" or "-200-RPM.txt") and assign that value to all '
                                             'BIST data parsed from that file.  The test units selected will be '
                                             'applied to all plots.\n\n'
                                             'For noise vs. azimuth tests, it is strongly recommended to use clear '
                                             'notation of the headings in filenames, such as "_123T_090S.txt" for '
                                             'a file collected at 123 deg True and heading 090 relative to the '
                                             'the prevailing seas (e.g., swell on the port side, where 000S '
                                             'corresponds to swell on the bow).\n\n'
                                             'The custom test params option below is intended only for particular '
                                             'data sets where the user has a very clear understanding of the test '
                                             'parameters (and consistent number of tests) in each file.')

        prm_min_tb_lbl = Label('Minimum param:', 120, 20, 'prm_min_tb_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        self.prm_min_tb = LineEdit('0', 40, 20, 'prm_min_tb', 'Enter the minimum speed')
        self.prm_min_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        prm_min_layout = BoxLayout([prm_min_tb_lbl, self.prm_min_tb], 'h', full_width=True)

        prm_max_tb_lbl = Label('Maximum param:', 120, 20, 'prm_max_tb_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        self.prm_max_tb = LineEdit('12', 40, 20, 'prm_max_tb', 'Enter the maximum speed')
        self.prm_max_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        prm_max_layout = BoxLayout([prm_max_tb_lbl, self.prm_max_tb], 'h', full_width=True)

        prm_int_tb_lbl = Label('Param interval:', 120, 20, 'prm_int_tb_lbl', (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        self.prm_int_tb = LineEdit('2', 40, 20, 'prm_min_tb', 'Enter the speed interval')
        self.prm_int_tb.setValidator(QDoubleValidator(0, np.inf, 1))
        prm_int_layout = BoxLayout([prm_int_tb_lbl, self.prm_int_tb], 'h', full_width=True)

        num_tests_tb_lbl = Label('Num. tests/interval:', 120, 20, 'num_tests_tb_lbl',
                                 (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        self.num_tests_tb = LineEdit('10', 40, 20, 'num_tests_tb', 'Enter the number of tests at each speed')
        self.num_tests_tb.setValidator(QDoubleValidator(0, np.inf, 0))
        prm_num_layout = BoxLayout([num_tests_tb_lbl, self.num_tests_tb], 'h', full_width=True)

        # total_num_params_tb_lbl = Label('Total num. intervals:', 120, 20, 'total_num_params_tb_lbl',
        #                                 (Qt.AlignRight | Qt.AlignVCenter))
        # self.total_num_params_tb = LineEdit('7', 40, 20, 'total_num_params_tb',
        #                                     'Total number of speeds in custom info')
        # self.total_num_params_tb.setEnabled(False)
        # total_prm_num_layout = BoxLayout([total_num_params_tb_lbl, self.total_num_params_tb], 'h')

        total_num_tests_tb_lbl = Label('Total num. tests:', 120, 20, 'total_num_tests_tb_lbl',
                                       (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        self.total_num_tests_tb = LineEdit('70', 40, 20, 'total_num_tests_tb',
                                           'Total number of tests in custom info')
        self.total_num_tests_tb.setEnabled(True)
        total_test_num_layout = BoxLayout([total_num_tests_tb_lbl, self.total_num_tests_tb], 'h', full_width=True)

        self.final_params_hdr = 'Params list: '
        self.final_params_lbl = Label(self.final_params_hdr + ', '.join([p for p in self.param_list]), 200, 20,
                                      'final_params_lbl', (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        self.final_params_lbl.setWordWrap(True)

        # custom_prm_layout = BoxLayout([prm_min_layout, prm_max_layout, prm_int_layout, prm_num_layout,
        #                                total_prm_num_layout, total_test_num_layout, self.final_params_lbl], 'v')

        custom_prm_layout = BoxLayout([prm_min_layout, prm_max_layout, prm_int_layout, prm_num_layout,
                                       total_test_num_layout, self.final_params_lbl], 'v', full_width=True)

        self.custom_param_gb = GroupBox('Use custom test params', custom_prm_layout, True, False, 'custom_params_gb')
        self.custom_param_gb.setToolTip('Enter custom test parameter information.  The total number of tests shown '
                                        'below must equal the total number of BISTs parsed from the selected files '
                                        '(total tests, not file count).\n\n'
                                        'The parameters will be associated with files in the order they are loaded '
                                        '(e.g., first BIST parsed will be associated with "minimium" parameter).')

        # param_layout = BoxLayout([prm_unit_layout, self.parse_test_params_gb, self.custom_param_gb], 'v')
        # param_layout = BoxLayout([prm_unit_layout, self.parse_test_params_gb, self.custom_param_gb], 'v')
        param_layout = BoxLayout([prm_unit_layout, self.prm_plot_lim_gb, self.binned_rxnoise_range_gb,
                                  self.binned_calculated_mean_gb, self.binned_error_type_gb,
                                  self.binned_individual_gb, self.parse_test_params_gb,
                                  self.plotting_test_params_gb, self.custom_param_gb], 'v', full_width=True)


        self.noise_test_gb = GroupBox('RX Noise Testing Plot Parameters', param_layout, False, False, 'noise_test_gb')

        # set up tabs
        self.tabs = QtWidgets.QTabWidget()

        # set up tab 2: combined filtering and advanced noise test options
        self.tab2 = QtWidgets.QWidget()
        # self.tab2.layout = BoxLayout([plot_btn_layout, param_layout], 'v')
        self.tab2.layout = BoxLayout([bist_options_layout], 'v')
        self.tab2.layout.addStretch()
        self.tab2.setLayout(self.tab2.layout)

        # set up tab 2: filtering options
        # self.tab2 = QtWidgets.QWidget()
        # self.tab2.layout = plot_btn_layout
        # self.tab2.layout.addStretch()
        # self.tab2.setLayout(self.tab2.layout)

        # set up tab 3: advanced options
        # self.tab3 = QtWidgets.QWidget()
        # self.tab3.layout = param_layout
        # self.tab3.layout.addStretch()
        # self.tab3.setLayout(self.tab3.layout)

        # add tabs to tab layout
        self.tabs.addTab(self.tab2, 'Plot')
        # self.tabs.addTab(self.tab3, 'Noise Test')

        self.tabw = 215  # set fixed tab width
        self.tabs.setFixedWidth(self.tabw)

        # stack file_control_gb and plot_control_gb
        self.right_layout = QtWidgets.QVBoxLayout()
        self.right_layout.addWidget(self.custom_info_gb)
        # Removed tabs from right layout - they're now in separate columns

    def set_left_layout(self):
        # add table showing selected files
        self.file_list = QtWidgets.QListWidget()
        self.file_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.installEventFilter(self)

        # set layout of file list
        self.file_list_layout = QtWidgets.QVBoxLayout()
        self.file_list_layout.addWidget(self.file_list)

        # set file list group box
        self.file_list_gb = QtWidgets.QGroupBox('Sources')
        self.file_list_gb.setLayout(self.file_list_layout)
        self.file_list_gb.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred)

        # add activity log widget
        self.log = QtWidgets.QTextEdit()
        # self.log.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
        #                        QtWidgets.QSizePolicy.MinimumExpanding)
        self.log.setStyleSheet("background-color: #404040; color: white; font-family: monospace;")
        self.log.setReadOnly(True)
        self.update_log('*** New BIST plotting log ***')

        # add progress bar for total file list
        self.current_fnum_lbl = QtWidgets.QLabel('Current file count:')
        self.calc_pb_lbl = QtWidgets.QLabel('Total Progress:')
        self.calc_pb = QtWidgets.QProgressBar()
        self.calc_pb.setGeometry(0, 0, 200, 30)
        self.calc_pb.setMaximum(100)  # this will update with number of files
        self.calc_pb.setValue(0)

        # set progress bar layout
        self.calc_pb_layout = QtWidgets.QHBoxLayout()
        self.calc_pb_layout.addWidget(self.calc_pb_lbl)
        self.calc_pb_layout.addWidget(self.calc_pb)

        self.prog_layout = QtWidgets.QVBoxLayout()
        self.prog_layout.addWidget(self.current_fnum_lbl)
        self.prog_layout.addLayout(self.calc_pb_layout)

        # set the log layout
        self.log_layout = QtWidgets.QVBoxLayout()
        self.log_layout.addWidget(self.log)
        self.log_layout.addLayout(self.prog_layout)

        # set the log group box widget with log layout
        self.log_gb = QtWidgets.QGroupBox('Activity Log')
        self.log_gb.setLayout(self.log_layout)

        # set the left panel layout with file controls on top and log on bottom
        self.left_layout = QtWidgets.QVBoxLayout()
        self.left_layout.addWidget(self.file_list_gb)
        self.left_layout.addWidget(self.log_gb)  # add log group box

    def set_main_layout(self):  # set the main layout with files tab on left, file list/log in middle, and controls on right
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Fixed side-column widths; only the middle plot area grows with the window
        left_col_w = 335
        right_col_w = 340

        # Left column: Sources (file list + controls), Plot, Activity Log
        left_column = QtWidgets.QVBoxLayout()
        left_column.setContentsMargins(0, 0, 0, 0)

        self.file_list_layout.addLayout(self.file_btn_layout)
        self.file_list_gb.setMinimumWidth(0)
        self.file_list_gb.setFixedWidth(315)
        self.file_list_gb.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Expanding)
        left_column.addWidget(self.file_list_gb, 1)

        plot_gb = QtWidgets.QGroupBox('Plot')
        plot_gb.setLayout(self.tab2.layout)
        plot_gb.setFixedWidth(315)
        left_column.addWidget(plot_gb)

        filter_gb = QtWidgets.QGroupBox('RX Noise Filtering')
        filter_gb.setFixedWidth(315)
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.setContentsMargins(8, 4, 8, 4)
        self.transient_filter_chk = CheckBox(
            'Transient Filter', False, 'transient_filter_chk',
            'Flag an RX noise test as a bad transient when the average level of all of its modules is above this dB value')
        self.transient_db_tb = LineEdit(
            '70', 55, 20, 'transient_db_tb',
            'dB threshold. A test at this level is kept; a test above it is a bad transient')
        self.transient_db_tb.setEnabled(False)
        self.transient_db_lbl = Label('dB', 24, 20, 'transient_db_lbl')
        filter_row.addWidget(self.transient_filter_chk)
        filter_row.addWidget(self.transient_db_tb)
        filter_row.addWidget(self.transient_db_lbl)
        filter_row.addStretch(1)
        null_row = QtWidgets.QHBoxLayout()
        null_row.setContentsMargins(8, 0, 8, 4)
        self.remove_nulls_chk = CheckBox(
            'Remove Null Values', True, 'remove_nulls_chk',
            'Leave RX noise module readings at or below 0 dB out of every RX noise plot. Does not add a chart.')
        null_row.addWidget(self.remove_nulls_chk)
        null_row.addStretch(1)
        filter_layout = QtWidgets.QVBoxLayout()
        filter_layout.addLayout(filter_row)
        filter_layout.addLayout(null_row)
        filter_gb.setLayout(filter_layout)
        left_column.addWidget(filter_gb)

        self.log_gb.setMinimumWidth(0)
        self.log_gb.setFixedWidth(315)
        self.log_gb.setMinimumHeight(260)
        self.log_gb.setMaximumHeight(260)
        left_column.addWidget(self.log_gb)
        left_column.addStretch(1)

        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_column)
        left_widget.setMinimumWidth(315)
        left_scroll = self._make_side_column_scroll(left_widget, left_col_w)

        # Middle column: Plot window only - expands with window resize
        middle_column = QtWidgets.QVBoxLayout()
        middle_column.setContentsMargins(0, 0, 0, 0)

        plot_window_gb = QtWidgets.QGroupBox('Plot Window')
        plot_window_layout = QtWidgets.QVBoxLayout()

        # Stack About view (startup) and matplotlib canvas (after plotting)
        self.plot_stack = QtWidgets.QStackedWidget()
        self.plot_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding)

        self.about_plot_widget = self._build_about_program_widget()
        self.plot_stack.addWidget(self.about_plot_widget)  # index 0

        # Initialize matplotlib figure for plot display
        # Start with a reasonable default size that will be adjusted when plots are loaded
        self.plot_figure = Figure(figsize=(8, 8))
        self.plot_figure_canvas = FigureCanvas(self.plot_figure)
        self.plot_figure_canvas.setMouseTracking(True)
        self.plot_figure_canvas.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding)
        self.plot_figure_canvas.setMinimumSize(0, 0)
        self.plot_stack.addWidget(self.plot_figure_canvas)  # index 1

        self._plot_window_layout = plot_window_layout
        plot_window_layout.addWidget(self.plot_stack, 1)  # stretch: fill plot window
        self.plot_stack.setCurrentWidget(self.about_plot_widget)

        # Add navigation controls for multiple charts
        nav_layout = QtWidgets.QHBoxLayout()

        # Previous button
        self.prev_chart_btn = QtWidgets.QPushButton("← Previous")
        self.prev_chart_btn.setToolTip("Show previous chart")
        self.prev_chart_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_chart_btn)

        # Chart indicator label
        self.freq_label = QtWidgets.QLabel("Chart: None")
        self.freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.freq_label.setStyleSheet("font-weight: bold; color: #2E86AB;")
        nav_layout.addWidget(self.freq_label)

        # Next button
        self.next_chart_btn = QtWidgets.QPushButton("Next →")
        self.next_chart_btn.setToolTip("Show next chart")
        self.next_chart_btn.setEnabled(False)
        nav_layout.addWidget(self.next_chart_btn)
        self.prev_chart_btn.clicked.connect(self.show_previous_frequency)
        self.next_chart_btn.clicked.connect(self.show_next_frequency)

        plot_window_layout.addLayout(nav_layout)
        plot_window_gb.setLayout(plot_window_layout)
        middle_column.addWidget(plot_window_gb, 1)

        middle_widget = QtWidgets.QWidget()
        middle_widget.setLayout(middle_column)
        middle_widget.setMinimumWidth(400)
        middle_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding)

        # Right column: System info and Plot section
        right_column = QtWidgets.QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)

        self.custom_info_gb.setFixedWidth(320)
        right_column.addWidget(self.custom_info_gb)

        self.noise_test_gb.setFixedWidth(320)
        right_column.addWidget(self.noise_test_gb)
        right_column.addStretch(1)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right_column)
        right_widget.setMinimumWidth(320)
        right_scroll = self._make_side_column_scroll(right_widget, right_col_w)

        # Side columns fixed width; middle column takes all remaining space
        main_layout.addWidget(left_scroll, 0)
        main_layout.addWidget(middle_widget, 1)
        main_layout.addWidget(right_scroll, 0)

        self.mainWidget.setLayout(main_layout)

    def _make_side_column_scroll(self, content_widget, fixed_width):
        """Fixed-width side column with scroll bars when content exceeds the window height."""
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(content_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFixedWidth(fixed_width)
        scroll.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Expanding)
        scroll.setMinimumHeight(0)
        return scroll

    def _set_noise_param_unit(self, unit_name):
        """Select a parameter unit in the RX Noise combo box if present."""
        unit_index = -1
        for i in range(self.prm_unit_cbox.count()):
            if self.prm_unit_cbox.itemText(i) == unit_name:
                unit_index = i
                break
        if unit_index >= 0:
            self.prm_unit_cbox.setCurrentIndex(unit_index)
            self.update_noise_param_unit()
        else:
            self.update_log(f'Warning: {unit_name} option not found in parameter unit dropdown')

    def _rx_noise_plot_test_type(self, test_type):
        """Map GUI test_type to plot_rx_noise test_type (pitch/RPM params use speed_bist)."""
        if test_type in ('speed', 'pitch_deg', 'pitch_pct', 'rpm'):
            return 'speed'
        return test_type

    def update_noise_param_string(self):  # update the dict of strings for parsing noise parameters from filenames
        self.noise_params[self.prm_unit_cbox.currentText()] = self.prm_str_tb.text()

    def _on_ignore_sis5_user_toggle(self, _state):
        """Remember when the user turns off Ignore SIS5 Speeds while SOG (kt) is selected."""
        if self._ignore_sis5_syncing:
            return
        if self.prm_unit_cbox.currentText() == 'SOG (kt)':
            self._ignore_sis5_user_disabled_on_sog = not self.ignore_sis5_speeds_chk.isChecked()

    def _apply_ignore_sis5_for_test_unit(self):
        """Check Ignore SIS5 Speeds for non-SOG units; restore on SOG unless user cleared it."""
        is_sog = self.prm_unit_cbox.currentText() == 'SOG (kt)'
        should_check = (not is_sog) or not self._ignore_sis5_user_disabled_on_sog
        self._ignore_sis5_syncing = True
        self.ignore_sis5_speeds_chk.setChecked(should_check)
        self._ignore_sis5_syncing = False

    def update_noise_param_unit(self):  # update text box with custom string for noise test unit
        self.prm_str_tb.setText(self.noise_params[self.prm_unit_cbox.currentText()])

        # enable current adjustment input fields if speed through water is selected
        self.current_tb.setEnabled('stw' in self.prm_unit_cbox.currentText().lower())
        self.current_dir_cbox.setEnabled('stw' in self.prm_unit_cbox.currentText().lower())
        self._apply_ignore_sis5_for_test_unit()

    def _plot_style_items(self):
        return [self.noise_test_type_cbox.itemText(i) for i in range(self.noise_test_type_cbox.count())]

    def _set_plot_style_items(self, items, select_text):
        """Replace Plot Style choices without emitting a plot."""
        self.noise_test_type_cbox.blockSignals(True)
        self.noise_test_type_cbox.clear()
        self.noise_test_type_cbox.addItems(items)
        index = self.noise_test_type_cbox.findText(select_text)
        if index < 0:
            index = 0
        self.noise_test_type_cbox.setCurrentIndex(index)
        self.noise_test_type_cbox.blockSignals(False)

    def _sync_plot_style_for_bist_type(self):
        """Show noise modes for RX Noise, or Plot All / History for channel BISTs."""
        want_noise = self.type_cbox.currentIndex() == 2
        items = self._plot_style_items()
        current = self.noise_test_type_cbox.currentText()
        if want_noise:
            if items == self._noise_plot_styles:
                if current in self._noise_plot_styles:
                    self._saved_noise_plot_style = current
            else:
                select = self._saved_noise_plot_style
                if select not in self._noise_plot_styles:
                    select = self._noise_plot_styles[0]
                self._set_plot_style_items(self._noise_plot_styles, select)
        else:
            if current in self._noise_plot_styles:
                self._saved_noise_plot_style = current
            if items == self._channel_plot_styles:
                if current in self._channel_plot_styles:
                    self._saved_channel_plot_style = current
            else:
                select = self._saved_channel_plot_style
                if select not in self._channel_plot_styles:
                    select = 'Plot All'
                self._set_plot_style_items(self._channel_plot_styles, select)
        self.noise_test_type_cbox.setEnabled(True)

    def _channel_history_only(self):
        return self.noise_test_type_cbox.currentText() == 'History'

    def update_buttons(self):  # update buttons/options from user actions
        self._sync_plot_style_for_bist_type()
        if self.type_cbox.currentIndex() == 2:  # noise testing
            self.noise_test_gb.setEnabled(True)
            self.noise_test_type_cbox.setEnabled(True)

            if self.prm_unit_cbox.currentIndex() != self.prm_unit_cbox.count() - 1:  # store last non-azimuth param unit
                self.prm_unit_cbox_last_index = self.prm_unit_cbox.currentIndex()

            if self.noise_test_type_cbox.currentText() == 'vs. Azimuth':  # disable custom param, enable swell tb
                self.prm_unit_cbox.setCurrentIndex(self.prm_unit_cbox.count()-1)
                self.prm_unit_cbox.setEnabled(False)
                self.prm_str_tb.setEnabled(False)
                # self.current_tb.setEnabled(False)
                # self.current_dir_cbox.setEn(False)
                self.swell_dir_tb.setEnabled(True)
                self.parse_test_params_gb.setChecked(True)
                self.custom_param_gb.setEnabled(False)
                self.update_swell_dir()

            elif self.noise_test_type_cbox.currentText() == 'vs. RPM':
                self._set_noise_param_unit('RPM')
                self.update_log('Parameter unit automatically set to RPM for RPM heatmap plots')
                self.prm_unit_cbox.setEnabled(True)
                self.prm_str_tb.setEnabled(True)
                self.swell_dir_tb.setEnabled(False)
                self.custom_param_gb.setEnabled(True)

            elif self.noise_test_type_cbox.currentText() == 'vs. RPM (Binned)':  # set parameter unit to RPM
                self._set_noise_param_unit('RPM')
                self.update_log('Parameter unit automatically set to RPM for RPM binned plots')
                self.binned_individual_cb.setCurrentIndex(0)
                self.update_log('Individual Points automatically set to Binned (Cyan) for RPM binned plots')
                self.prm_unit_cbox.setEnabled(True)
                self.prm_str_tb.setEnabled(True)
                self.swell_dir_tb.setEnabled(False)
                self.custom_param_gb.setEnabled(True)

            elif self.noise_test_type_cbox.currentText() == 'vs. Pitch (deg)':
                self._set_noise_param_unit('Pitch (deg)')
                self.update_log('Parameter unit automatically set to Pitch (deg) for pitch heatmap plots')
                self.prm_unit_cbox.setEnabled(True)
                self.prm_str_tb.setEnabled(True)
                self.swell_dir_tb.setEnabled(False)
                self.custom_param_gb.setEnabled(True)

            elif self.noise_test_type_cbox.currentText() == 'vs. Pitch (Binned) - deg':
                self._set_noise_param_unit('Pitch (deg)')
                self.update_log('Parameter unit automatically set to Pitch (deg) for pitch binned plots')
                self.binned_individual_cb.setCurrentIndex(0)
                self.prm_unit_cbox.setEnabled(True)
                self.prm_str_tb.setEnabled(True)
                self.swell_dir_tb.setEnabled(False)
                self.custom_param_gb.setEnabled(True)

            elif self.noise_test_type_cbox.currentText() == 'vs. Pitch (%)':
                self._set_noise_param_unit('Pitch (%)')
                self.update_log('Parameter unit automatically set to Pitch (%) for pitch heatmap plots')
                self.prm_unit_cbox.setEnabled(True)
                self.prm_str_tb.setEnabled(True)
                self.swell_dir_tb.setEnabled(False)
                self.custom_param_gb.setEnabled(True)

            elif self.noise_test_type_cbox.currentText() == 'vs. Pitch (Binned) - %':
                self._set_noise_param_unit('Pitch (%)')
                self.update_log('Parameter unit automatically set to Pitch (%) for pitch binned plots')
                self.binned_individual_cb.setCurrentIndex(0)
                self.prm_unit_cbox.setEnabled(True)
                self.prm_str_tb.setEnabled(True)
                self.swell_dir_tb.setEnabled(False)
                self.custom_param_gb.setEnabled(True)

            else:  # noise vs speed / custom parameter; enable custom param, disable swell tb
                self.prm_unit_cbox.setCurrentIndex(self.prm_unit_cbox_last_index)
                self.prm_unit_cbox.setEnabled(True)
                self.prm_str_tb.setEnabled(True)
                self.swell_dir_tb.setEnabled(False)
                self.custom_param_gb.setEnabled(True)

                # if 'stw' in self.prm_unit_cbox.currentText().lower(): # enable current adjustments to SOG for STW calc
                #     self.current_tb.setEnabled(True)
                #     self.current_dir_cbox.setEn(True)

        else:
            self.noise_test_gb.setEnabled(False)
            self.noise_test_type_cbox.setEnabled(True)

        self.prm_str_tb.setText(self.noise_params[self.prm_unit_cbox.currentText()])
        
        # Automatically select BIST files that support the chosen plot type
        if self.file_list.count() > 0:  # Only if there are files loaded
            self.select_bist()

    def update_groupboxes(self):  # toggle groupbox checked state
        if self.noise_test_type_cbox.currentText() == 'vs. Azimuth':
            return

        else:
            self.gb_toggle = not self.gb_toggle
            self.parse_test_params_gb.setChecked(self.gb_toggle)
            self.custom_param_gb.setChecked(not self.gb_toggle)
            
            # Update total tests when custom parameters group box is enabled
            # Check the new state (not self.gb_toggle) since custom_param_gb is set to not self.gb_toggle
            if not self.gb_toggle:  # This means custom_param_gb is now checked
                self.update_log('Custom parameters enabled - updating total tests count')
                self.update_log(f'Current gb_toggle state: {self.gb_toggle}')
                self.update_log(f'Custom param group box checked: {self.custom_param_gb.isChecked()}')
                self.update_total_tests_from_files()
            else:
                self.update_log('Custom parameters disabled - not updating total tests count')

    def update_binned_rxnoise_range(self):  # enable/disable RX noise range Min/Max text boxes
        """Enable or disable the Min/Max text boxes based on group box state"""
        is_checked = self.binned_rxnoise_range_gb.isChecked()
        self.binned_rxnoise_min_tb.setEnabled(is_checked)
        self.binned_rxnoise_max_tb.setEnabled(is_checked)

    def _on_calculated_mean_changed(self, mean_text):
        """Match the error-bar type to the mean the user just selected."""
        error_for_mean = {
            'Linear Mean': 'Standard Deviation Linear',
            'Arithmetic Mean': 'Standard Deviation Arithmetic',
            'Arithmetic & Linear Mean': 'Standard Deviation Linear',
        }
        error_text = error_for_mean.get(mean_text)
        if error_text:
            index = self.binned_error_type_cb.findText(error_text)
            if index >= 0 and index != self.binned_error_type_cb.currentIndex():
                self.binned_error_type_cb.blockSignals(True)
                self.binned_error_type_cb.setCurrentIndex(index)
                self.binned_error_type_cb.blockSignals(False)
        self.auto_update_plot()

    def _binned_calculated_mean(self):
        """Which calculated means to draw. 'None' hides both when the group is unchecked."""
        if not self.binned_calculated_mean_gb.isChecked():
            return 'None'
        return self.binned_calculated_mean_cb.currentText()

    def _rx_noise_range_lims(self):
        """Return [min, max] dB when the RX noise range box is checked and valid, else []."""
        if not self.binned_rxnoise_range_gb.isChecked():
            return []
        try:
            return [float(self.binned_rxnoise_min_tb.text()),
                    float(self.binned_rxnoise_max_tb.text())]
        except ValueError:
            self.update_log('Warning: Invalid RX noise range values, using default range')
            return []

    def _apply_detected_bist_type(self):
        """Set the BIST pulldown from loaded files: RX noise, then TX, then RX channels."""
        found = set()
        for path in self.filenames:
            if not path:
                continue
            bist_type, _sis = read_bist.verify_bist_type(path)
            found.update(bist_type)
        # Combo box is TX, RX channels, RX noise (bist_list indexes 1, 2, 3).
        if 3 in found:
            combo_index = 2
        elif 1 in found:
            combo_index = 0
        elif 2 in found:
            combo_index = 1
        else:
            return
        self.type_cbox.blockSignals(True)
        self.type_cbox.setCurrentIndex(combo_index)
        self.type_cbox.blockSignals(False)
        self.update_buttons()
        self._set_plot_selected_pending(True)
        self.update_log('BIST type set to ' + self.type_cbox.currentText())

    def add_files(self, ftype_filter, input_dir='HOME', include_subdir=False):  # add all files of specified type in dir
        if input_dir == 'HOME':  # select files manually if input_dir not specified as optional argument
            # Load last used input directory from session config
            config = load_bist_session_config()
            # Use USERPROFILE on Windows, HOME on Unix-like systems
            default_dir = os.getenv('USERPROFILE') or os.getenv('HOME') or os.getcwd()
            last_input_dir = config.get("last_input_directory", default_dir)
            
            fnames = QtWidgets.QFileDialog.getOpenFileNames(self, 'Open files...', last_input_dir, ftype_filter)
            fnames = fnames[0]  # keep only the filenames in first list item returned from getOpenFileNames
            
            # Save the directory of the first selected file to session config
            if fnames:
                first_file_dir = os.path.dirname(fnames[0])
                update_bist_last_directory("last_input_directory", first_file_dir)

        else:  # get all files satisfying ftype_filter in input_dir
            fnames = []

            if include_subdir:  # walk through all subdirectories
                for dirpath, dirnames, filenames in os.walk(input_dir):
                    for filename in [f for f in filenames if f.endswith(ftype_filter)]:
                        fnames.append(os.path.join(dirpath, filename))

            else:  # step through all files in this directory only (original method)
                for f in os.listdir(input_dir):
                    if os.path.isfile(os.path.join(input_dir, f)):  # verify it's a file
                        if os.path.splitext(f)[1] == ftype_filter:  # verify ftype_filter extension
                            fnames.append(os.path.join(input_dir, f))  # add whole path, same as getOpenFileNames

        # get updated file list and add selected files only if not already listed
        self.get_current_file_list()
        fnames_new = [fn for fn in fnames if fn not in self.filenames]
        fnames_skip = [fs for fs in fnames if fs in self.filenames]

        if len(fnames_skip) > 0:  # skip any files already added, update log
            self.update_log('Skipping ' + str(len(fnames_skip)) + ' file(s) already added')

        added_any = False
        for f in range(len(fnames_new)):  # add the new files only after verifying BIST type
            bist_type, sis_ver_found = read_bist.verify_bist_type(fnames_new[f])
            print(bist_type, sis_ver_found)

            if 0 not in bist_type:  # add files only if plotters are available for tests in file (test types  > 0)
                # add item with full file path data, set text according to show/hide path button
                [path, fname] = fnames_new[f].rsplit('/', 1)
                # print('path=', path)
                # print('fname=', fname)
                # add file only if name exists prior to ext (may slip through splitext check if adding directory)
                if fname.rsplit('.', 1)[0]:
                    new_item = QtWidgets.QListWidgetItem()
                    new_item.setData(1, fnames_new[f].replace('\\','/'))  # set full file path as data, role 1
                    new_item.setText((path + '/') * int(self.show_path_chk.isChecked()) + fname)  # set text, show path
                    self.file_list.addItem(new_item)
                    added_any = True
                    self._clear_startup_action_highlight()
                    # self.update_log('Added ' + fname)  # fnames_new[f].rsplit('/',1)[-1])
                    bist_types_found = [self.bist_list[idx_found] for idx_found in bist_type]
                    self.update_log('Added ' + fnames_new[f].split('/')[-1] +
                                    ' (SIS ' + str(sis_ver_found) + ': ' +
                                    ', '.join(bist_types_found) + ')')

                else:
                    self.update_log('Skipping empty filename ' + fname)

            else:  # skip non-verified BIST types
                self.update_log('Skipping ' + fnames_new[f].split('/')[-1] + ' (' + self.bist_list[0] + ')')

        self.get_current_file_list()  # update self.file_list and file count
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))
        if fnames_new:
            self._sn_user_entered = False
            self._model_user_entered = False
            self._date_user_entered = False
            self._freq_user_entered = False
            self.sn_updated = False
            self._title_chk_user.difference_update(('model', 'sn', 'date', 'frequency'))
            self._clear_export_button_highlight()
        if added_any:
            self._apply_detected_bist_type()

    def show_file_paths(self):
        # show or hide path for all items in file_list according to show_paths_chk selection
        for i in range(self.file_list.count()):
            [path, fname] = self.file_list.item(i).data(1).rsplit('/', 1)  # split full file path from item data, role 1
            self.file_list.item(i).setText((path+'/')*int(self.show_path_chk.isChecked()) + fname)

    def get_input_dir(self):
        try:
            # Load last used input directory from session config
            config = load_bist_session_config()
            # Use USERPROFILE on Windows, HOME on Unix-like systems
            default_dir = os.getenv('USERPROFILE') or os.getenv('HOME') or os.getcwd()
            last_input_dir = config.get("last_input_directory", default_dir)
            
            self.input_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add directory', last_input_dir)
            
            if self.input_dir:  # Only proceed if user didn't cancel
                self._clear_startup_action_highlight()
                # Save the selected directory to session config
                update_bist_last_directory("last_input_directory", self.input_dir)
                
                self.update_log('Added directory: ' + self.input_dir)

                # get a list of all .txt files in that directory, '/' avoids '\\' in os.path.join in add_files
                self.update_log('Adding files in directory: ' + self.input_dir)
                self.add_files(ftype_filter='.txt', input_dir=self.input_dir+'/',
                               include_subdir=self.include_subdir_chk.isChecked())

        except ValueError:
            self.update_log('No input directory selected.')
            self.input_dir = ''
            pass

    def _clear_startup_action_highlight(self):
        """Return the startup buttons to normal text after files, a directory, or an analysis are loaded."""
        if not getattr(self, '_startup_action_pending', False):
            return
        self._startup_action_pending = False
        self.add_file_btn.setStyleSheet(self._export_btn_style_default)
        self.get_indir_btn.setStyleSheet(self._export_btn_style_default)
        self.import_analysis_btn.setStyleSheet(self._export_btn_style_default)

    def _clear_export_button_highlight(self):
        """Reset export button text color after export or when input data changes."""
        self._export_pending = False
        self.export_plots_btn.setStyleSheet(self._export_btn_style_default)
        self.export_analysis_btn.setStyleSheet(self._export_btn_style_default)

    def _set_export_button_pending(self):
        """Highlight export buttons in orange until export or new data is loaded."""
        self._export_pending = True
        self.export_plots_btn.setStyleSheet(self._export_btn_style_pending)
        self.export_analysis_btn.setStyleSheet(self._export_btn_style_pending)

    def _update_export_button(self, mark_pending=False):
        """Enable export and set label based on number of plots from the last run."""
        n = len(self.all_figures) if hasattr(self, 'all_figures') and self.all_figures else 0
        self.export_plots_btn.setText('Export Plots')
        self.export_plots_btn.setEnabled(n > 0)
        self.export_analysis_btn.setEnabled(n > 0)
        if mark_pending and n > 0:
            self._set_export_button_pending()
        elif n == 0:
            self._clear_export_button_highlight()

    def _export_rx_noise_chart(self, plot_data, output_dir):
        """Export one RX noise figure using arguments matching its plot type."""
        plot_type = plot_data.get('plot_type', '')
        test_type = plot_data.get('test_type', 'speed')
        bist_plot = plot_data['bist']

        if plot_type == 'rx_noise':
            read_bist.plot_rx_noise(
                bist_plot,
                save_figs=True,
                output_dir=output_dir,
                test_type=self._rx_noise_plot_test_type(test_type),
                param=plot_data.get('param', []),
                param_unit=plot_data.get('param_unit', 'SOG (kt)'),
                param_adjust=plot_data.get('param_adjust', 0.0),
                param_lims=plot_data.get('param_lims', []),
                noise_lims=self._rx_noise_range_lims(),
                cmap=plot_data.get('cmap', 'jet'),
                sort=plot_data.get('sort', 'ascending'),
                redblue_center=plot_data.get('redblue_center', 55),
                return_fig=False,
                gui_embed=True)
            return

        plot_fn = plot_data.get('plot_function')
        if plot_fn is None:
            self.update_log(f'Warning: No export handler for RX noise plot type {plot_type!r}')
            return

        plot_test_type = 'speed' if test_type in (
            'speed_binned', 'speed_binned_2kt', 'rpm_binned',
            'pitch_binned_deg', 'pitch_binned_pct') else test_type
        result = plot_fn(
            bist_plot,
            save_figs=True,
            output_dir=output_dir,
            test_type=plot_test_type,
            param=plot_data.get('param', []),
            param_unit=plot_data.get('param_unit', 'SOG (kt)'),
            param_adjust=plot_data.get('param_adjust', 0.0),
            param_lims=plot_data.get('param_lims', []),
            binned_range_lims=plot_data.get('binned_range_lims', []),
            error_bar_type=plot_data.get('error_bar_type', 'Standard Deviation Linear'),
            individual_type=plot_data.get('individual_type', 'Non-binned (Light Grey)'),
            calculated_mean=plot_data.get('calculated_mean', 'Arithmetic & Linear Mean'),
            sort=plot_data.get('sort', 'ascending'),
            source_heatmap=plot_data.get('source_heatmap', False),
            cmap=plot_data.get('cmap', 'jet'),
            redblue_center=plot_data.get('redblue_center', 55),
            return_fig=False)
        if isinstance(result, tuple):
            result = result[0]

    def _remember_transient_filter_applied(self):
        self._transient_filter_applied = (
            self.transient_filter_chk.isChecked(),
            self.transient_db_tb.text().strip())

    def _transient_threshold_db(self):
        """Threshold used for this plot, or None when the filter is off or the value is not numeric."""
        if not self.transient_filter_chk.isChecked():
            return None
        text = self.transient_db_tb.text().strip()
        try:
            return float(text)
        except ValueError:
            self.update_log('Transient filter: enter a numeric dB threshold')
            return None

    def _on_transient_filter_changed(self, *_args):
        checked = self.transient_filter_chk.isChecked()
        self.transient_db_tb.setEnabled(checked)
        if self._transient_filter_syncing:
            return
        applied = (checked, self.transient_db_tb.text().strip())
        if applied == self._transient_filter_applied:
            return
        self._remember_transient_filter_applied()
        if self.type_cbox.currentIndex() != 2:
            return
        if not getattr(self, 'all_figures', None):
            return
        if not self.file_list.selectedItems():
            return
        self.plot_bist()

    def _on_remove_nulls_changed(self, *_args):
        if self._transient_filter_syncing:
            return
        if self.type_cbox.currentIndex() != 2:
            return
        if not getattr(self, 'all_figures', None):
            return
        if not self.file_list.selectedItems():
            return
        self.plot_bist()

    def _transient_freq_label(self, bist):
        try:
            freq = bist['frequency'][0][0]
        except Exception:
            return ''
        if isinstance(freq, (list, tuple)):
            freq = freq[0] if freq else ''
        return str(freq).strip()

    def _iter_transient_variants(self, bist, param):
        """(tag, bist, param) pairs. One untagged pair unless a test is above the threshold."""
        threshold = self._active_transient_threshold
        if threshold is None:
            return [('', bist, param)]
        bad = read_bist.transient_test_indexes(bist, threshold)
        total = read_bist.rx_noise_test_count(bist)
        freq = self._transient_freq_label(bist)
        where = f' ({freq})' if freq else ''
        if not bad:
            self.update_log(f'Transient filter{where}: no tests above {threshold:g} dB')
            return [('', bist, param)]
        filtered_bist, filtered_param = read_bist.drop_rx_noise_tests(bist, param, bad)
        raw = copy.deepcopy(bist)
        raw['title_suffix'] = 'Raw'
        if filtered_bist is None:
            self.update_log(
                f'Transient filter{where}: all {total} tests are above {threshold:g} dB; showing raw data only')
            return [('Raw', raw, param)]
        filtered_bist['title_suffix'] = 'Filtered'
        self.update_log(f'Transient filter{where}: {len(bad)} of {total} tests above {threshold:g} dB')
        return [('Raw', raw, param), ('Filtered', filtered_bist, filtered_param)]

    def _emit_rx_noise_charts(self, bist, param, plot_data, base_name, make_figure, source_fn=None):
        """Add the usual chart, or a Raw chart and a Filtered chart when tests are flagged."""
        names = []
        for tag, bist_i, param_i in self._iter_transient_variants(bist, param):
            if self.remove_nulls_chk.isChecked():
                bist_i = read_bist.mask_rx_noise_nulls(bist_i)
            # Stamp the user's system info after tests are removed, so the
            # filtered chart cannot fall back to a different file's values.
            self._apply_sn_title_metadata(bist_i)
            data = dict(plot_data)
            data['bist'] = bist_i
            data['param'] = param_i
            result = make_figure(bist_i, param_i)
            figure = result[0] if isinstance(result, tuple) else result
            if figure is None:
                continue
            self.frequency_data.append(data)
            self.all_figures.append(figure)
            label = f'{base_name} ({tag})' if tag else str(base_name)
            names.append(label)
            if source_fn is not None and self._append_binned_source_heatmap(data, source_fn):
                if tag:
                    names.append(f'{base_name} ({tag}, BISTs)')
                else:
                    names.append(f'{base_name} (BISTs)')
        return names

    def _append_binned_source_heatmap(self, plot_data, plot_fn):
        """Add the binned plot plus the heatmap of BISTs that filled each bin."""
        source_data = dict(plot_data)
        source_data['source_heatmap'] = True
        source_data['plot_type'] = 'rx_noise_binned_sources'
        source_data['cmap'] = self.cmap_cbox.currentText().lower().strip()
        source_data['redblue_center'] = self.redblue_center_spin.value()
        try:
            result = plot_fn(
                source_data['bist'],
                save_figs=False,
                output_dir=self.output_dir,
                test_type='speed',
                param=source_data.get('param', []),
                param_unit=source_data.get('param_unit', 'SOG (kt)'),
                param_adjust=source_data.get('param_adjust', 0.0),
                param_lims=source_data.get('param_lims', []),
                binned_range_lims=source_data.get('binned_range_lims', []),
                error_bar_type=source_data.get('error_bar_type', 'Standard Deviation Linear'),
                individual_type=source_data.get('individual_type', 'Non-binned (Light Grey)'),
                calculated_mean=source_data.get('calculated_mean', 'Arithmetic & Linear Mean'),
                sort=source_data.get('sort', 'ascending'),
                source_heatmap=True,
                cmap=source_data['cmap'],
                redblue_center=source_data['redblue_center'],
                return_fig=True)
            figure = result[0] if isinstance(result, tuple) else result
            if figure is None:
                self.update_log('Binned source heatmap was not created')
                return False
            self.frequency_data.append(source_data)
            self.all_figures.append(figure)
            self.total_charts = len(self.all_figures)
            return True
        except Exception as e:
            self.update_log(f'Error generating binned source heatmap: {e}')
            return False

    def _binned_source_kwargs(self, plot_data):
        """Colormap arguments for the binned-plus-heatmap chart."""
        if not plot_data.get('source_heatmap'):
            return {}
        return {
            'source_heatmap': True,
            'cmap': plot_data.get('cmap', self.cmap_cbox.currentText().lower().strip()),
            'redblue_center': plot_data.get('redblue_center', self.redblue_center_spin.value()),
        }

    def _prompt_export_directory(self):
        """Ask user for export directory; remember choice between sessions."""
        config = load_bist_session_config()
        default_dir = config.get("last_output_directory",
                                 os.getenv('USERPROFILE') or os.getenv('HOME') or os.getcwd())
        new_output_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select directory to save plots', default_dir)
        if new_output_dir:
            self.output_dir = new_output_dir.replace('/', '\\')
            update_bist_last_directory("last_output_directory", new_output_dir)
            return self.output_dir
        return None

    def export_plots(self):
        """Export all plots and text reports from the last Plot BIST run."""
        output_dir = self._begin_plot_export()
        if not output_dir:
            return
        try:
            n_plots = self._export_plot_files(output_dir)
            self.update_log(f'Exported {n_plots} plot(s) and reports to {output_dir}')
            QtWidgets.QMessageBox.information(
                self, 'Export complete',
                f'Saved plot files to:\n{output_dir}')
            self._clear_export_button_highlight()
        except Exception as e:
            self._report_export_error(e)
        finally:
            self._close_export_figures()

    def export_analysis(self):
        """Export the plots and a JSON file that can recreate them."""
        output_dir = self._begin_plot_export()
        if not output_dir:
            return
        try:
            n_plots = self._export_plot_files(output_dir)
            started = self._export_started
            plot_names = self._plots_written_since(output_dir, started)
            json_path = self._write_analysis_json(output_dir, plot_names)
            self.update_log(f'Exported {n_plots} plot(s), reports, and analysis file to {output_dir}')
            QtWidgets.QMessageBox.information(
                self, 'Export complete',
                f'Saved plot files and analysis to:\n{output_dir}\n\n{os.path.basename(json_path)}')
            self._clear_export_button_highlight()
        except Exception as e:
            self._report_export_error(e)
        finally:
            self._close_export_figures()

    def _begin_plot_export(self):
        """Confirm a plot exists and ask where to save. Returns the directory, or None."""
        if not getattr(self, 'all_figures', None) or len(self.all_figures) == 0:
            QtWidgets.QMessageBox.warning(self, 'Export', 'No plots to export. Use Plot BIST first.')
            return None
        if not self.last_plotted_bist:
            QtWidgets.QMessageBox.warning(self, 'Export', 'No plot data available to export.')
            return None
        output_dir = self._prompt_export_directory()
        if not output_dir:
            self.update_log('Export cancelled.')
            return None
        self.update_log(f'Exporting to {output_dir}...')
        self._export_started = datetime.datetime.now().timestamp()
        return output_dir

    def _export_plot_files(self, output_dir):
        """Write PNG plots and out-of-spec reports for the last plot run."""
        bist = self.last_plotted_bist
        bist_test_type = self.last_bist_test_type
        if bist_test_type == self.bist_list[1]:  # TX Channels
            tx_oos = read_bist.write_tx_out_of_spec_report(bist, output_dir=output_dir)
            if tx_oos:
                self.update_log(f'Wrote {len(tx_oos)} TX out-of-spec report(s)')
            history_only = self.last_channel_plot_style == 'History'
            if not history_only:
                for ps in [1, 2]:
                    read_bist.plot_tx_z(bist, plot_style=ps, save_figs=True, output_dir=output_dir)
            f_hist = read_bist.plot_tx_z_history(bist, save_figs=True, output_dir=output_dir)
            if f_hist:
                self.update_log(f'Saved TX history plot {f_hist}')
        elif bist_test_type == self.bist_list[2]:  # RX Channels
            rx_oos = read_bist.write_rx_array_out_of_spec_report(bist, output_dir=output_dir)
            if rx_oos:
                self.update_log(f'Wrote {len(rx_oos)} RX array out-of-spec report(s)')
            history_only = self.last_channel_plot_style == 'History'
            if not history_only:
                read_bist.plot_rx_z(bist, save_figs=True, output_dir=output_dir)
                read_bist.plot_rx_z_line_heatmap(bist, save_figs=True, output_dir=output_dir)
            read_bist.plot_rx_z_history(bist, save_figs=True, output_dir=output_dir)
        elif bist_test_type == self.bist_list[3]:  # RX Noise
            for plot_data in self.frequency_data:
                self._export_rx_noise_chart(plot_data, output_dir)
        return len(self.all_figures)

    def _report_export_error(self, error):
        self.update_log(f'Error during export: {error}')
        import traceback
        self.update_log(traceback.format_exc())
        QtWidgets.QMessageBox.critical(self, 'Export failed', str(error))

    def _close_export_figures(self):
        import matplotlib.pyplot as plt
        for fig_num in plt.get_fignums():
            fig = plt.figure(fig_num)
            if fig not in getattr(self, 'all_figures', []):
                plt.close(fig)

    def _analysis_colormap_uses_center(self, colormap):
        return colormap in ('RedBlue', 'CoolWarm', 'Reversed Managua')

    def _analysis_record(self):
        """Settings needed to recreate the current plot."""
        files = list(getattr(self, 'last_plotted_files', []) or [])
        if not files:
            files = [(self.file_list.item(i).data(1) or '').replace('\\', '/')
                     for i in range(self.file_list.count())
                     if self.file_list.item(i).isSelected()]
        colormap = self.cmap_cbox.currentText()
        record = {
            'version': 1,
            'files': files,
            'into_seas_file': self.last_into_seas_file,
            'bist_type': self.type_cbox.currentText(),
            'plot_noise': self.noise_test_type_cbox.currentText() or None,
            'colormap': colormap,
            'system_information': {
                'model': self.model_cbox.currentText(),
                'serial_number': self.sn_tb.text().strip(),
                'ship_name': self._optional_sysinfo_text(self.ship_tb),
                'description': self._optional_sysinfo_text(self.cruise_tb),
                'date': self.date_tb.text().strip(),
                'frequency': self.freq_tb.text().strip(),
                'show_in_title': {
                    'model': self.model_title_chk.isChecked(),
                    'serial_number': self.sn_title_chk.isChecked(),
                    'frequency': self.freq_title_chk.isChecked(),
                    'ship_name': self.ship_title_chk.isChecked(),
                    'description': self.cruise_title_chk.isChecked(),
                    'date': self.date_title_chk.isChecked(),
                },
            },
            'plot_parameters': {
                'test_units': self.prm_unit_cbox.currentText(),
                'filename_string': self.prm_str_tb.text(),
                'sort_order': self.sort_cbox.currentText(),
                'ignore_sis5_speeds': self.ignore_sis5_speeds_chk.isChecked(),
                'x_axis_limits_enabled': self.prm_plot_lim_gb.isChecked(),
                'x_axis_min': self.prm_plot_min_tb.text(),
                'x_axis_max': self.prm_plot_max_tb.text(),
                'rx_noise_range_enabled': self.binned_rxnoise_range_gb.isChecked(),
                'rx_noise_min': self.binned_rxnoise_min_tb.text(),
                'rx_noise_max': self.binned_rxnoise_max_tb.text(),
                'calculated_mean_enabled': self.binned_calculated_mean_gb.isChecked(),
                'calculated_mean': self.binned_calculated_mean_cb.currentText(),
                'error_bars_enabled': self.binned_error_type_gb.isChecked(),
                'error_bar_type': self.binned_error_type_cb.currentText(),
                'individual_measurements_enabled': self.binned_individual_gb.isChecked(),
                'individual_measurements': self.binned_individual_cb.currentText(),
                'parse_test_params': self.parse_test_params_gb.isChecked(),
                'current_kt': self.current_tb.text(),
                'current_direction': self.current_dir_cbox.currentText(),
                'swell_direction_deg': self.swell_dir_tb.text(),
                'custom_test_params': self.custom_param_gb.isChecked(),
                'custom_minimum': self.prm_min_tb.text(),
                'custom_maximum': self.prm_max_tb.text(),
                'custom_interval': self.prm_int_tb.text(),
                'custom_tests_per_interval': self.num_tests_tb.text(),
                'custom_total_tests': self.total_num_tests_tb.text(),
                'transient_filter': self.transient_filter_chk.isChecked(),
                'transient_filter_db': self.transient_db_tb.text().strip(),
                'remove_null_values': self.remove_nulls_chk.isChecked(),
            },
        }
        if self._analysis_colormap_uses_center(colormap):
            record['colormap_center'] = self.redblue_center_spin.value()
        return record

    def _plots_written_since(self, output_dir, started):
        """PNG plot files written or updated during this export."""
        written = []
        try:
            names = os.listdir(output_dir)
        except OSError:
            return written
        for fname in names:
            if not fname.lower().endswith('.png'):
                continue
            path = os.path.join(output_dir, fname)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime >= started - 1.0:
                written.append((mtime, fname))
        written.sort()
        return [fname for _mtime, fname in written]

    def _write_analysis_json(self, output_dir, plot_names):
        """Write one analysis JSON named from the first plot saved in this export."""
        if not plot_names:
            raise RuntimeError('No plot files were saved, so no analysis file was written.')
        stem = os.path.splitext(plot_names[0])[0]
        json_path = os.path.join(output_dir, stem + '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self._analysis_record(), f, indent=2)
        self.update_log(f'Wrote analysis file {os.path.basename(json_path)}')
        return json_path

    def import_analysis(self):
        """Load an analysis JSON file, restore its settings, and plot again."""
        config = load_bist_session_config()
        default_dir = config.get('last_output_directory',
                                 os.getenv('USERPROFILE') or os.getenv('HOME') or os.getcwd())
        json_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Import analysis', default_dir, 'Analysis JSON (*.json)')
        if not json_path:
            self.update_log('Import cancelled.')
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                record = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            QtWidgets.QMessageBox.critical(self, 'Import failed', f'Could not read analysis file:\n{e}')
            return
        if not isinstance(record, dict) or not record.get('files'):
            QtWidgets.QMessageBox.warning(self, 'Import failed', 'This JSON file does not contain an analysis file list.')
            return
        self._clear_startup_action_highlight()
        files = [str(p).replace('\\', '/') for p in record['files']]
        missing = [p for p in files if not os.path.isfile(p)]
        if missing:
            listed = '\n'.join(missing)
            self.update_log('Import stopped. Missing BIST file(s):\n' + listed)
            QtWidgets.QMessageBox.warning(
                self, 'Import failed',
                'These BIST files from the analysis could not be found:\n\n' + listed)
            return
        try:
            self._restore_analysis(record, files)
        except Exception as e:
            self.update_log(f'Error importing analysis: {e}')
            import traceback
            self.update_log(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, 'Import failed', str(e))
            return
        self.update_log(f'Imported analysis from {json_path}')
        self.plot_bist()
        if not getattr(self, 'all_figures', None):
            QtWidgets.QMessageBox.warning(self, 'Import', 'Settings were restored, but no plots were created.')
            return
        QtWidgets.QMessageBox.information(self, 'Import complete', 'The analysis plots have been recreated.')

    def _restore_analysis(self, record, files):
        """Load analysis files and put the saved settings back into the controls."""
        self.all_figures = []
        self.frequency_data = []
        self.total_charts = 0
        self.current_chart_index = 0
        self._update_export_button()

        failed = self._add_verified_bist_files(files)
        if failed:
            raise RuntimeError('Could not add BIST file(s):\n' + '\n'.join(failed))

        params = record.get('plot_parameters') or {}
        sys_info = record.get('system_information') or {}
        plot_noise = record.get('plot_noise')
        if plot_noise == 'vs. Azimuth':
            swell = str(params.get('swell_direction_deg', '')).strip()
            if swell and swell != self.swell_dir_default:
                self.swell_dir_tb.setText(swell)
                self.swell_dir_updated = True

        self._apply_analysis_system_info(sys_info)

        self.type_cbox.blockSignals(True)
        self.noise_test_type_cbox.blockSignals(True)
        try:
            bist_type = record.get('bist_type', '')
            type_index = self.type_cbox.findText(bist_type)
            if type_index < 0:
                raise RuntimeError(f'BIST type {bist_type!r} is not available.')
            self.type_cbox.setCurrentIndex(type_index)
            if plot_noise in self._noise_plot_styles:
                self._saved_noise_plot_style = plot_noise
                noise_index = self.noise_test_type_cbox.findText(plot_noise)
                if noise_index >= 0:
                    self.noise_test_type_cbox.setCurrentIndex(noise_index)
            elif plot_noise in self._channel_plot_styles:
                self._saved_channel_plot_style = plot_noise
            elif plot_noise:
                raise RuntimeError(f'Plot style {plot_noise!r} is not available.')
        finally:
            self.type_cbox.blockSignals(False)
            self.noise_test_type_cbox.blockSignals(False)
        self.update_buttons()

        if plot_noise != 'vs. Azimuth' and params.get('test_units'):
            self._set_noise_param_unit(params['test_units'])
        if params.get('filename_string') is not None:
            self.prm_str_tb.setText(str(params['filename_string']))
            self.noise_params[self.prm_unit_cbox.currentText()] = self.prm_str_tb.text()
        if params.get('sort_order'):
            sort_index = self.sort_cbox.findText(params['sort_order'])
            if sort_index >= 0:
                self.sort_cbox.setCurrentIndex(sort_index)
        if 'ignore_sis5_speeds' in params:
            self._ignore_sis5_syncing = True
            self.ignore_sis5_speeds_chk.setChecked(bool(params['ignore_sis5_speeds']))
            self._ignore_sis5_syncing = False
            if self.prm_unit_cbox.currentText() == 'SOG (kt)':
                self._ignore_sis5_user_disabled_on_sog = not self.ignore_sis5_speeds_chk.isChecked()

        self.prm_plot_lim_gb.setChecked(bool(params.get('x_axis_limits_enabled', False)))
        self.prm_plot_min_tb.setText(str(params.get('x_axis_min', self.prm_plot_min_tb.text())))
        self.prm_plot_max_tb.setText(str(params.get('x_axis_max', self.prm_plot_max_tb.text())))
        self.binned_rxnoise_range_gb.setChecked(bool(params.get('rx_noise_range_enabled', True)))
        self.binned_rxnoise_min_tb.setText(str(params.get('rx_noise_min', self.binned_rxnoise_min_tb.text())))
        self.binned_rxnoise_max_tb.setText(str(params.get('rx_noise_max', self.binned_rxnoise_max_tb.text())))
        self.binned_calculated_mean_gb.setChecked(bool(params.get('calculated_mean_enabled', True)))
        mean_index = self.binned_calculated_mean_cb.findText(params.get('calculated_mean', ''))
        if mean_index >= 0:
            self.binned_calculated_mean_cb.setCurrentIndex(mean_index)
        self.binned_error_type_gb.setChecked(bool(params.get('error_bars_enabled', True)))
        saved_error = {
            'Standard Deviation': 'Standard Deviation Linear',
            'Standard Error': 'Standard Error Linear',
        }.get(params.get('error_bar_type', ''), params.get('error_bar_type', ''))
        error_index = self.binned_error_type_cb.findText(saved_error)
        if error_index >= 0:
            self.binned_error_type_cb.setCurrentIndex(error_index)
        self.binned_individual_gb.setChecked(bool(params.get('individual_measurements_enabled', True)))
        individual_index = self.binned_individual_cb.findText(params.get('individual_measurements', ''))
        if individual_index >= 0:
            self.binned_individual_cb.setCurrentIndex(individual_index)
        if 'parse_test_params' in params:
            self.parse_test_params_gb.setChecked(bool(params['parse_test_params']))
        self._transient_filter_syncing = True
        try:
            if 'transient_filter' in params:
                self.transient_filter_chk.setChecked(bool(params['transient_filter']))
            if params.get('transient_filter_db') is not None:
                self.transient_db_tb.setText(str(params['transient_filter_db']))
            self.transient_db_tb.setEnabled(self.transient_filter_chk.isChecked())
            if 'remove_null_values' in params:
                self.remove_nulls_chk.setChecked(bool(params['remove_null_values']))
            self._remember_transient_filter_applied()
        finally:
            self._transient_filter_syncing = False
        self.current_tb.setText(str(params.get('current_kt', self.current_tb.text())))
        current_index = self.current_dir_cbox.findText(params.get('current_direction', ''))
        if current_index >= 0:
            self.current_dir_cbox.setCurrentIndex(current_index)
        if params.get('swell_direction_deg') is not None:
            self.swell_dir_tb.setText(str(params['swell_direction_deg']))
            self.swell_dir_updated = self.swell_dir_tb.text().strip() not in ('', self.swell_dir_default)

        self.prm_min_tb.setText(str(params.get('custom_minimum', self.prm_min_tb.text())))
        self.prm_max_tb.setText(str(params.get('custom_maximum', self.prm_max_tb.text())))
        self.prm_int_tb.setText(str(params.get('custom_interval', self.prm_int_tb.text())))
        self.num_tests_tb.setText(str(params.get('custom_tests_per_interval', self.num_tests_tb.text())))
        if params.get('custom_total_tests') is not None:
            self.total_num_tests_tb.setText(str(params['custom_total_tests']))
        self.custom_param_gb.setChecked(bool(params.get('custom_test_params', False)))
        if self.custom_param_gb.isChecked():
            self.update_param_info()

        colormap = record.get('colormap')
        if colormap:
            self.cmap_cbox.blockSignals(True)
            cmap_index = self.cmap_cbox.findText(colormap)
            if cmap_index < 0:
                self.cmap_cbox.blockSignals(False)
                raise RuntimeError(f'Colormap {colormap!r} is not available.')
            self.cmap_cbox.setCurrentIndex(cmap_index)
            self.cmap_cbox.blockSignals(False)
            self.redblue_center_spin.setVisible(self._analysis_colormap_uses_center(colormap))
        if 'colormap_center' in record:
            self.redblue_center_spin.setValue(float(record['colormap_center']))

        wanted = set(files)
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item.setSelected((item.data(1) or '').replace('\\', '/') in wanted)
        into_seas = record.get('into_seas_file')
        if into_seas:
            into_seas = str(into_seas).replace('\\', '/')
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if (item.data(1) or '').replace('\\', '/') == into_seas:
                    self.set_file_into_seas(item, True)
                    break
        if params.get('swell_direction_deg') is not None:
            self.swell_dir_tb.setText(str(params['swell_direction_deg']))
            self.swell_dir_updated = self.swell_dir_tb.text().strip() not in ('', self.swell_dir_default)

    def _apply_analysis_system_info(self, sys_info):
        """Restore system-information fields and keep file verification from replacing them."""
        model = sys_info.get('model', '')
        model_index = self.model_cbox.findText(model)
        if model and model_index >= 0:
            self.model_cbox.setCurrentIndex(model_index)
            self.model_updated = True
        serial = str(sys_info.get('serial_number', '')).strip()
        self._sn_programmatic_update = True
        self.sn_tb.setText(serial)
        self._sn_programmatic_update = False
        self._sn_user_entered = bool(serial)
        self.sn_updated = bool(serial)
        ship = str(sys_info.get('ship_name', '')).strip()
        if self._is_undefined_sysinfo(ship):
            self._set_optional_sysinfo_undefined(self.ship_tb)
        else:
            self.ship_tb.setText(ship)
            self.ship_tb.setStyleSheet('color: cyan;')
        description = str(sys_info.get('description', '')).strip()
        if self._is_undefined_sysinfo(description):
            self._set_optional_sysinfo_undefined(self.cruise_tb)
        else:
            self.cruise_tb.setText(description)
            self.cruise_tb.setStyleSheet('color: cyan;')
        if sys_info.get('date') is not None:
            self.date_tb.setText(str(sys_info['date']))
            self.date_updated = True
        frequency = str(sys_info.get('frequency', '')).strip()
        if frequency:
            self._sysinfo_programmatic_update = True
            self.freq_tb.setText(frequency)
            self._sysinfo_programmatic_update = False
            self._freq_user_entered = not self._is_undefined_sysinfo(frequency)
            self._freq_autofill_text = frequency
        show = sys_info.get('show_in_title') or {}
        title_checks = (
            ('model', self.model_title_chk),
            ('serial_number', self.sn_title_chk),
            ('frequency', self.freq_title_chk),
            ('ship_name', self.ship_title_chk),
            ('description', self.cruise_title_chk),
            ('date', self.date_title_chk),
        )
        for key, checkbox in title_checks:
            checkbox.blockSignals(True)
            checkbox.setChecked(bool(show.get(key, key != 'frequency')))
            checkbox.blockSignals(False)
            self._title_chk_user.add(key)
        self.refresh_system_info_from_ui()

    def _add_verified_bist_files(self, paths):
        """Add BIST paths that are not already listed. Returns paths that could not be added."""
        self.get_current_file_list()
        existing = {(p or '').replace('\\', '/') for p in self.filenames}
        failed = []
        for raw in paths:
            path = str(raw).replace('\\', '/')
            if path in existing:
                continue
            bist_type, sis_ver_found = read_bist.verify_bist_type(path)
            if not bist_type or 0 in bist_type:
                failed.append(path)
                continue
            parts = path.rsplit('/', 1)
            if len(parts) != 2 or not parts[1].rsplit('.', 1)[0]:
                failed.append(path)
                continue
            file_path, fname = parts
            new_item = QtWidgets.QListWidgetItem()
            new_item.setData(1, path)
            new_item.setText((file_path + '/') * int(self.show_path_chk.isChecked()) + fname)
            self.file_list.addItem(new_item)
            existing.add(path)
            bist_types_found = [self.bist_list[idx] for idx in bist_type if idx < len(self.bist_list)]
            self.update_log('Added ' + fname + ' (SIS ' + str(sis_ver_found) + ': ' +
                            ', '.join(bist_types_found) + ')')
        self.get_current_file_list()
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))
        return failed

    # def remove_files(self, clear_all=False):  # remove selected files
    #     self.get_current_file_list()
    #     selected_files = self.file_list.selectedItems()
    #
    #     if clear_all:  # clear all
    #         self.file_list.clear()
    #         self.filenames = []
    #         self.update_log('All files have been removed.')
    #
    #     elif self.filenames and not selected_files:  # files exist but nothing is selected
    #         self.update_log('No files selected for removal.')
    #         return
    #
    #     else:  # remove only the files that have been selected
    #         for f in selected_files:
    #             fname = f.text().split('/')[-1]
    #             self.file_list.takeItem(self.file_list.row(f))
    #             self.update_log('Removed ' + fname)

    def remove_bist_files(self, clear_all=False):  # remove selected files
        # remove selected files or clear all files, update det and spec dicts accordingly
        removed_files = remove_files(self, clear_all)
        self.get_current_file_list()
        if removed_files or clear_all:
            self._clear_export_button_highlight()

        if self.filenames == []:  # all files have been removed
            self._set_plot_selected_pending(False)
            if clear_all:
                self._clear_shown_plots()
            self.update_log('Cleared all files')
            self.cruise_name_updated = False
            self.model_updated = False
            self.ship_name_updated = False
            self.sn_updated = False
            self._sn_user_entered = False
            self._model_user_entered = False
            self._date_user_entered = False
            self._freq_user_entered = False
            self._title_chk_user.clear()
            self._set_title_checkbox(self.model_title_chk, True)
            self._set_title_checkbox(self.sn_title_chk, True)
            self._set_title_checkbox(self.freq_title_chk, False)
            self._set_title_checkbox(self.date_title_chk, True)
            self._sysinfo_programmatic_update = True
            self.freq_tb.setText('?')
            self._sysinfo_programmatic_update = False
            self.freq_tb.setStyleSheet('color: white;')
            self._freq_autofill_text = '?'
            self._set_title_checkbox(self.ship_title_chk, not self._is_undefined_sysinfo(self.ship_tb.text()))
            self._set_title_checkbox(self.cruise_title_chk, not self._is_undefined_sysinfo(self.cruise_tb.text()))
            self.swell_dir_updated = False
            self.swell_dir_tb.setText(self.swell_dir_default)
            self.swell_dir_message = True

    def get_current_file_list(self):  # get current list of files in qlistwidget
        list_items = []
        for f in range(self.file_list.count()):
            list_items.append(self.file_list.item(f))

        # self.filenames = [f.text() for f in list_items]  # convert to text
        self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1

        # self.filenames = [f.data(1) for f in list_items]  # return list of full file paths stored in item data, role 1
        self.current_fnum_lbl.setText('Current file count: ' + str(len(self.filenames)))
        
        # Update total number of tests based on loaded files
        self.update_total_tests_from_files()

    def update_total_tests_from_files(self):
        """Update the total number of tests field based on loaded BIST files"""
        # Only update if custom parameters group box is enabled
        if not self.custom_param_gb.isChecked():
            self.update_log('Custom parameters not enabled - skipping total tests update')
            return
            
        self.update_log(f'Updating total tests from {len(self.filenames)} loaded files')
            
        try:
            total_tests = 0
            rx_noise_files = 0
            for filename in self.filenames:
                if filename:  # Check if filename is not empty
                    # Try to parse the BIST file to get test count
                    try:
                        bist_type, sis_ver_found = read_bist.verify_bist_type(filename)
                        self.update_log(f'File {filename.split("/")[-1]}: BIST types {bist_type}, SIS version {sis_ver_found}')
                        if bist_type and 3 in bist_type:  # RX Noise BIST
                            rx_noise_files += 1
                            # Parse the file to get test count
                            bist_temp = read_bist.parse_rx_noise(filename, sis_version=sis_ver_found)
                            if bist_temp and 'test' in bist_temp:
                                file_tests = len(bist_temp['test'])  # test is a list of test numbers
                                total_tests += file_tests
                                self.update_log(f'File {filename.split("/")[-1]}: {file_tests} tests')
                            else:
                                self.update_log(f'File {filename.split("/")[-1]}: No test data found')
                        else:
                            self.update_log(f'File {filename.split("/")[-1]}: Not an RX Noise BIST')
                    except Exception as e:
                        # If parsing fails, continue with next file
                        self.update_log(f'Error parsing {filename.split("/")[-1]}: {str(e)}')
                        continue
            
            self.update_log(f'Summary: Found {rx_noise_files} RX Noise files with {total_tests} total tests')
            if total_tests > 0:
                self.total_num_tests_tb.setText(str(total_tests))
                self.update_log(f'Updated total number of tests to {total_tests} based on loaded BIST files')
            else:
                self.total_num_tests_tb.setText('0')
                self.update_log('No RX Noise tests found in loaded files')
        except Exception as e:
            self.update_log(f'Error updating total tests: {str(e)}')
            self.total_num_tests_tb.setText('0')

    def update_total_tests_from_selected_files(self):
        """Update the total number of tests field based on selected BIST files"""
        try:
            total_tests = 0
            selected_files = [self.file_list.item(f).data(1) for f in range(self.file_list.count())
                             if self.file_list.item(f).isSelected()]
            
            # Only proceed if we have selected files
            if not selected_files:
                self.total_num_tests_tb.setText('0')
                return
            
            for filename in selected_files:
                if filename:  # Check if filename is not empty
                    # Try to parse the BIST file to get test count
                    try:
                        bist_type, sis_ver_found = read_bist.verify_bist_type(filename)
                        if bist_type and 3 in bist_type:  # RX Noise BIST
                            # Parse the file to get test count
                            bist_temp = read_bist.parse_rx_noise(filename, sis_version=sis_ver_found)
                            if bist_temp and 'test' in bist_temp:
                                # Count total tests (test is a list of test numbers)
                                total_tests += len(bist_temp['test'])
                    except Exception as e:
                        # If parsing fails, continue with next file
                        self.update_log(f'Warning: Could not parse {filename.split("/")[-1]} for test count')
                        continue
            
            if total_tests > 0:
                self.total_num_tests_tb.setText(str(total_tests))
                self.update_log(f'Updated total number of tests to {total_tests} based on selected RX Noise BIST files')
            else:
                self.total_num_tests_tb.setText('0')
                self.update_log('No RX Noise tests found in selected files')
        except Exception as e:
            self.update_log(f'Error updating total tests from selected files: {str(e)}')
            self.total_num_tests_tb.setText('0')

    def get_new_file_list(self, fext=[''], flist_old=[]):
        # determine list of new files with file extension fext that do not exist in flist_old
        # flist_old may contain paths as well as file names; compare only file names
        self.get_current_file_list()
        fnames_ext = [fn for fn in self.filenames if any(ext in fn for ext in fext)]  # fnames (w/ paths) matching ext
        fnames_old = [fn.split('/')[-1] for fn in flist_old]  # file names only (no paths) from flist_old
        fnames_new = [fn for fn in fnames_ext if fn.split('/')[-1] not in fnames_old]  # check if fname in fnames_old

        return fnames_new  # return the fnames_new (with paths)

    def select_bist(self):
        # verify BIST types in current file list and select those matching current BIST type in combo box
        self.clear_bist()  # update file list and clear all selections before re-selecting those of desired BIST type
        bist_count = 0  # count total selected files
        
        current_bist_type = self.type_cbox.currentIndex() + 1  # currentIndex+1 because bist_list starts at 0 = N/A
        self.update_log(f'Selecting BIST type {current_bist_type} ({self.type_cbox.currentText()})')

        for f in range(len(self.filenames)):  # loop through file list and select if matches BIST type in combo box
            # bist_type, sis_ver_found = read_bist.verify_bist_type(self.file_list.item(f).text())
            bist_type, sis_ver_found = read_bist.verify_bist_type(self.file_list.item(f).data(1))

            # check whether selected test index from combo box  is available in this file
            if current_bist_type in bist_type:  # currentIndex+1 because bist_list starts at 0 = N/A
                self.file_list.item(f).setSelected(True)
                bist_count = bist_count+1

        if bist_count == 0:  # update log with selection total
            self.update_log('No ' + self.type_cbox.currentText() + ' files available for selection')

        else:
            self.update_log('Selected ' + str(bist_count) + ' ' + self.type_cbox.currentText() + ' file(s)')

        self.verify_system_info(warn=self.warn_user_chk.isChecked())

    def clear_bist(self):
        self.get_current_file_list()
        for f in range(len(self.filenames)):
            self.file_list.item(f).setSelected(False)  # clear any pre-selected items before re-selecting verified ones

    def _is_undefined_sysinfo(self, text):
        """True when a ship name or description has not been entered."""
        return str(text).strip() in ('', '?')

    def _optional_sysinfo_text(self, widget):
        """Ship name or description for titles and saved data; '' while unset."""
        text = widget.text().strip()
        return '' if self._is_undefined_sysinfo(text) else text

    def _set_optional_sysinfo_undefined(self, widget):
        """Show a magenta ? until the user enters a ship name or description."""
        widget.blockSignals(True)
        widget.setText('?')
        widget.blockSignals(False)
        widget.setStyleSheet('color: magenta;')

    def _refresh_optional_sysinfo_style(self, widget):
        if self._is_undefined_sysinfo(widget.text()):
            widget.setStyleSheet('color: magenta;')
        else:
            widget.setStyleSheet('color: white;')

    def _finalize_optional_sysinfo(self, widget):
        if self._is_undefined_sysinfo(widget.text()):
            self._set_optional_sysinfo_undefined(widget)
        else:
            widget.setStyleSheet('color: cyan;')

    def _system_info_snapshot(self):
        """Tuple of current system-information field values for change detection."""
        return (
            self.model_cbox.currentText().replace('EM', '').strip(),
            self.sn_tb.text().strip(),
            self._optional_sysinfo_text(self.ship_tb),
            self._optional_sysinfo_text(self.cruise_tb),
            self.date_tb.text().strip(),
        )

    def _title_checkboxes(self):
        """System-information checkboxes that control plot titles."""
        return {
            'model': self.model_title_chk,
            'sn': self.sn_title_chk,
            'frequency': self.freq_title_chk,
            'ship_name': self.ship_title_chk,
            'cruise_name': self.cruise_title_chk,
            'date': self.date_title_chk,
        }

    def _set_title_checkbox(self, checkbox, checked):
        """Set a title checkbox without treating it as a user click."""
        if checkbox.isChecked() == bool(checked):
            return
        checkbox.blockSignals(True)
        checkbox.setChecked(bool(checked))
        checkbox.blockSignals(False)

    def _on_title_checkbox_toggled(self, field):
        """Keep a checkbox the user clicked from being changed by the next file check."""
        self._title_chk_user.add(field)
        self._replot_sysinfo_if_shown()

    def _sync_parsed_title_checkboxes(self):
        """Uncheck model, serial number, and date when files leave them unknown or conflicting."""
        problems = set(self.missing_fields) | set(self.conflicting_fields)
        for field in ('model', 'sn', 'date'):
            if field in self._title_chk_user:
                continue
            self._set_title_checkbox(self._title_checkboxes()[field], field not in problems)

    def _apply_sn_title_metadata(self, bist):
        """Tell plot titles which system-info fields to show, hide, or replace."""
        if bist is None:
            return
        self.refresh_system_info_from_ui()
        sn_user = bool(getattr(self, '_sn_user_entered', False))
        model_user = bool(getattr(self, '_model_user_entered', False))
        date_user = bool(getattr(self, '_date_user_entered', False))
        hide = set()
        if not self.model_title_chk.isChecked():
            hide.add('model')
        if not self.sn_title_chk.isChecked():
            hide.add('sn')
        if not self.freq_title_chk.isChecked():
            hide.add('frequency')
        if not self.ship_title_chk.isChecked():
            hide.add('ship_name')
        if not self.cruise_title_chk.isChecked():
            hide.add('cruise_name')
        if not self.date_title_chk.isChecked():
            hide.add('date')
        if sn_user and not self.sn_tb.text().strip():
            hide.add('sn')
        if date_user and not read_bist.defined_date_text(self.date_tb.text()):
            hide.add('date')
        freq_user = bool(getattr(self, '_freq_user_entered', False))
        if freq_user and self._is_undefined_sysinfo(self.freq_tb.text()):
            hide.add('frequency')
        bist['title_hide'] = hide
        bist['frequency_user_entered'] = freq_user
        bist['frequency_user_value'] = self.freq_tb.text().strip()
        bist['sn_user_entered'] = sn_user
        bist['sn_user_value'] = self.sn_tb.text().strip()
        bist['model_user_entered'] = model_user
        bist['model_user_value'] = self.model_number
        bist['date_user_entered'] = date_user
        bist['date_user_value'] = self.date_tb.text().strip()
        ship = self._optional_sysinfo_text(self.ship_tb)
        description = self._optional_sysinfo_text(self.cruise_tb)
        if 'ship_name' in bist:
            bist['ship_name'] = [ship for _ in bist['ship_name']] if isinstance(bist['ship_name'], list) else ship
        if 'cruise_name' in bist:
            bist['cruise_name'] = [description for _ in bist['cruise_name']] if isinstance(bist['cruise_name'], list) else description
        if model_user:
            self._replace_sysinfo_list(bist, 'model', self.model_number)
        if sn_user:
            self._replace_sysinfo_list(bist, 'sn', self.sn_tb.text().strip())
        if date_user:
            self._replace_sysinfo_list(bist, 'date', self.date_tb.text().strip())

    def _replace_sysinfo_list(self, bist, key, value):
        """Write one user-entered system-info value into every file slot."""
        current = bist.get(key)
        if isinstance(current, list) and current:
            bist[key] = [value for _ in current]
        elif key in bist:
            bist[key] = [value]

    def refresh_system_info_from_ui(self):
        """Read system information fields into instance attributes."""
        self.model_number, self.sn, self.ship_name, self.cruise_name, self.date_str = self._system_info_snapshot()

    def update_system_info(self):
        """Refresh stored system info; mark the edited field cyan when user commits a value."""
        self.refresh_system_info_from_ui()
        sender = self.sender()
        sys_info_widgets = (self.model_cbox, self.sn_tb, self.freq_tb, self.ship_tb, self.cruise_tb, self.date_tb)
        if sender not in sys_info_widgets:
            return

        if sender in (self.ship_tb, self.cruise_tb):
            self._finalize_optional_sysinfo(sender)
        else:
            sender.setStyleSheet('color: cyan')
        if sender.objectName() in self.missing_fields:
            self.missing_fields.remove(sender.objectName())

    def _mark_sysinfo_user_edit(self, field_name):
        """Treat a real edit as the value to show, even when files still disagree."""
        if field_name == 'sn':
            self._sn_user_entered = True
        elif field_name == 'model':
            self._model_user_entered = True
        elif field_name == 'date':
            self._date_user_entered = True
        elif field_name == 'frequency':
            self._freq_user_entered = True
        checkbox = self._title_checkboxes().get(field_name)
        if checkbox is not None:
            self._title_chk_user.add(field_name)
            self._set_title_checkbox(checkbox, True)
        if field_name in self.conflicting_fields:
            self.conflicting_fields.remove(field_name)
            self.update_sys_info_colors()

    def _replot_sysinfo_if_shown(self):
        if getattr(self, '_sysinfo_replot_active', False):
            return
        self._sysinfo_replot_active = True
        try:
            self.auto_update_plots_for_system_info()
        finally:
            self._sysinfo_replot_active = False

    def _on_optional_sysinfo_edited(self, field):
        """Show ship name or description in titles after the user enters one."""
        self._finalize_optional_sysinfo(field)
        key = 'ship_name' if field is self.ship_tb else 'cruise_name'
        known = not self._is_undefined_sysinfo(field.text())
        if known:
            self._title_chk_user.add(key)
        else:
            self._title_chk_user.discard(key)
        self._set_title_checkbox(self._title_checkboxes()[key], known)
        if field.hasFocus():
            return
        self._replot_sysinfo_if_shown()

    def _on_sn_user_edited(self):
        """Remember a serial number the user confirmed, including the value already shown."""
        if getattr(self, '_sn_programmatic_update', False):
            return
        already = self._sn_user_entered
        same = self.sn_tb.text().strip() == getattr(self, '_sn_autofill_text', None)
        self._mark_sysinfo_user_edit('sn')
        if self.sn_tb.hasFocus():
            return
        self.update_system_info()
        if already and same:
            return
        self._replot_sysinfo_if_shown()

    def _on_date_user_edited(self):
        """Remember a date the user typed, and drop it from titles if they clear it."""
        if getattr(self, '_sysinfo_programmatic_update', False):
            return
        if self.date_tb.text().strip() == getattr(self, '_date_autofill_text', None):
            return
        self._mark_sysinfo_user_edit('date')
        if self.date_tb.hasFocus():
            return
        self.update_system_info()
        self._replot_sysinfo_if_shown()

    def _on_freq_user_edited(self):
        """Use a frequency the user typed in plot titles."""
        if getattr(self, '_sysinfo_programmatic_update', False):
            return
        if self.freq_tb.text().strip() == getattr(self, '_freq_autofill_text', None):
            return
        self._mark_sysinfo_user_edit('frequency')
        if self.freq_tb.hasFocus():
            return
        self.update_system_info()
        self._replot_sysinfo_if_shown()

    def on_system_info_committed(self):
        """Apply system info after Enter or model selection; replot if plots are already shown."""
        sender = self.sender()
        if sender == self.sn_tb:
            self._mark_sysinfo_user_edit('sn')
        elif sender == self.model_cbox:
            self._mark_sysinfo_user_edit('model')
        elif sender == self.date_tb and self.date_tb.text().strip() != getattr(self, '_date_autofill_text', None):
            self._mark_sysinfo_user_edit('date')
        elif sender == self.freq_tb and self.freq_tb.text().strip() != getattr(self, '_freq_autofill_text', None):
            self._mark_sysinfo_user_edit('frequency')
        self.update_system_info()
        self._replot_sysinfo_if_shown()

    def auto_update_plots_for_system_info(self):
        """Re-run plotting with updated system info (all chart types)."""
        if not getattr(self, 'all_figures', None) or len(self.all_figures) == 0:
            return
        chart_index = self.current_chart_index
        self.update_log('Updating plots after system information change...')
        self.plot_bist()
        if self.all_figures and 0 <= chart_index < self.total_charts:
            self.current_chart_index = chart_index
            self.display_current_frequency()
            self.update_navigation_controls()
        if self.all_figures:
            self._update_export_button(mark_pending=True)

    def trigger_auto_update(self):
        """Trigger auto-update for RX noise / plot parameter fields (Enter key)."""
        self.refresh_system_info_from_ui()
        self.auto_update_plot()
    
    def _set_plot_selected_pending(self, pending):
        """Bold orange Plot Selected when a new BIST type or plot style is ready to plot."""
        style = self._export_btn_style_pending if pending else self._export_btn_style_default
        self.plot_bist_btn.setStyleSheet(style)

    def auto_plot_bist_type(self, _index=None):
        """Highlight Plot Selected when the user changes BIST type and a loaded file contains that type."""
        if self.file_list.count() == 0:
            self._set_plot_selected_pending(False)
            return
        bist_type = self.type_cbox.currentText()
        if len(self.file_list.selectedItems()) == 0:
            self._set_plot_selected_pending(False)
            self.update_log('No ' + bist_type + ' data in the loaded files')
            QtWidgets.QMessageBox.warning(
                self, 'BIST type',
                'None of the loaded files contain ' + bist_type + ' data.')
            return
        self._set_plot_selected_pending(True)
        self.update_log(bist_type + ' files are ready to plot')

    def auto_plot_noise_type(self):
        """Highlight Plot Selected when the user changes Plot Style and files of this BIST type are selected."""
        if self.file_list.count() == 0 or len(self.file_list.selectedItems()) == 0:
            self._set_plot_selected_pending(False)
            return
        if not self.noise_test_type_cbox.currentText():
            self._set_plot_selected_pending(False)
            return
        self._set_plot_selected_pending(True)
        self.update_log(self.noise_test_type_cbox.currentText() + ' is ready to plot')

    def _on_colormap_changed(self, _text=None):
        """Redraw the current RX noise heatmap with the colormap just selected."""
        cmap = self.cmap_cbox.currentText().lower().strip()
        center = self.redblue_center_spin.value()
        for plot_data in getattr(self, 'frequency_data', []) or []:
            if plot_data.get('plot_type') in ('rx_noise', 'rx_noise_binned_sources'):
                plot_data['cmap'] = cmap
                plot_data['redblue_center'] = center
        if not self.frequency_data or not (0 <= self.current_chart_index < len(self.frequency_data)):
            return
        if self.frequency_data[self.current_chart_index].get('plot_type') not in ('rx_noise', 'rx_noise_binned_sources'):
            return
        self.auto_update_plot()

    def auto_update_plot(self):
        """Auto-update plot when system info or RX noise testing settings change"""
        # Only auto-update if we have files loaded and a plot has been generated
        if (hasattr(self, 'all_figures') and len(self.all_figures) > 0 and 
            hasattr(self, 'current_chart_index') and self.current_chart_index >= 0):
            try:
                # Check if we have the necessary data to regenerate the current plot
                if (hasattr(self, 'frequency_data') and len(self.frequency_data) > 0 and 
                    self.current_chart_index < len(self.frequency_data)):
                    self.update_log("Auto-updating plot due to setting change...")
                    # Regenerate the current plot
                    self.regenerate_current_plot()
                else:
                    self.update_log("No frequency data available for auto-update")
            except Exception as e:
                self.update_log(f"Auto-update failed: {e}")
                import traceback
                self.update_log(f"Traceback: {traceback.format_exc()}")

    def regenerate_current_plot(self):
        """Regenerate the current plot with updated settings"""
        try:
            if (hasattr(self, 'frequency_data') and len(self.frequency_data) > 0 and 
                self.current_chart_index < len(self.frequency_data)):
                
                # Get the current frequency data
                current_freq_data = self.frequency_data[self.current_chart_index]
                
                # Clear the current plot
                self.plot_figure.clear()
                
                # Regenerate the plot using the stored data
                if 'plot_function' in current_freq_data:
                    plot_function = current_freq_data['plot_function']
                    
                    # Update the stored data with current settings
                    current_freq_data['error_bar_type'] = self.binned_error_type_cb.currentText()
                    current_freq_data['individual_type'] = self.binned_individual_cb.currentText()
                    current_freq_data['calculated_mean'] = self._binned_calculated_mean()
                    current_freq_data['model'] = self.model_number
                    current_freq_data['sn'] = self.sn
                    current_freq_data['ship_name'] = self.ship_name
                    current_freq_data['description'] = self.cruise_name
                    current_freq_data['date'] = self.date_str
                    
                    # Update RX Noise Testing parameters
                    current_freq_data['param_unit'] = self.prm_unit_cbox.currentText()
                    
                    # Recalculate param_lims if X-axis limits are enabled
                    if self.prm_plot_lim_gb.isChecked():
                        current_freq_data['param_lims'] = [float(self.prm_plot_min_tb.text()), float(self.prm_plot_max_tb.text())]
                    else:
                        current_freq_data['param_lims'] = []
                    
                    # Recalculate param_adjust for STW
                    param_adjust = 0.0
                    if 'stw' in self.prm_unit_cbox.currentText().lower():
                        param_adjust = float(self.current_tb.text())
                        param_adjust *= float([-1 if 'with' in self.current_dir_cbox.currentText().lower() else 1][0])
                    current_freq_data['param_adjust'] = param_adjust
                    
                    # RX noise range: binned Y-axis and heatmap color ramp
                    binned_range_lims = self._rx_noise_range_lims()
                    current_freq_data['binned_range_lims'] = binned_range_lims
                    current_freq_data['sort'] = self.sort_cbox.currentText().lower().strip()
                    if current_freq_data.get('plot_type') == 'rx_noise':
                        current_freq_data['cmap'] = self.cmap_cbox.currentText().lower().strip()
                        current_freq_data['redblue_center'] = self.redblue_center_spin.value()
                    
                    # Update the BIST data structure with new system info for title generation
                    bist_data = current_freq_data['bist']
                    if 'model' in bist_data:
                        bist_data['model'] = [self.model_number]
                    if 'sn' in bist_data:
                        bist_data['sn'] = [self.sn]
                    if 'ship_name' in bist_data:
                        bist_data['ship_name'] = [self.ship_name]
                    if 'cruise_name' in bist_data:
                        bist_data['cruise_name'] = [self.cruise_name]
                    if 'date' in bist_data:
                        bist_data['date'] = [self.date_str]
                    self._apply_sn_title_metadata(bist_data)
                    
                    # Debug: Log the updated values
                    self.update_log(f"Updated values - Model: {self.model_number}, SN: {self.sn}, Ship: {self.ship_name}, Date: {self.date_str}")
                    self.update_log(f"Updated RX Noise params - Unit: {current_freq_data['param_unit']}, Adjust: {param_adjust}, Limits: {current_freq_data['param_lims']}")
                    
                    self.update_log(f"Regenerating {current_freq_data['test_type']} plot...")
                    
                    # Regenerate the plot with updated parameters
                    if current_freq_data['test_type'] == 'speed_binned_2kt':
                        result = plot_function(current_freq_data['bist'], save_figs=False,
                                             output_dir=self.output_dir,
                                             test_type='speed',
                                             param=current_freq_data['param'],
                                             param_unit=current_freq_data['param_unit'],
                                             param_adjust=current_freq_data['param_adjust'],
                                             param_lims=current_freq_data['param_lims'],
                                             binned_range_lims=current_freq_data['binned_range_lims'],
                                             error_bar_type=current_freq_data['error_bar_type'],
                                             individual_type=current_freq_data['individual_type'],
                                             calculated_mean=current_freq_data.get('calculated_mean', 'Arithmetic & Linear Mean'),
                                             sort=current_freq_data.get('sort', 'ascending'),
                                             return_fig=True,
                                             **self._binned_source_kwargs(current_freq_data))
                    elif current_freq_data['test_type'] == 'speed_binned':
                        result = plot_function(current_freq_data['bist'], save_figs=False,
                                             output_dir=self.output_dir,
                                             test_type='speed',
                                             param=current_freq_data['param'],
                                             param_unit=current_freq_data['param_unit'],
                                             param_adjust=current_freq_data['param_adjust'],
                                             param_lims=current_freq_data['param_lims'],
                                             binned_range_lims=current_freq_data['binned_range_lims'],
                                             error_bar_type=current_freq_data['error_bar_type'],
                                             individual_type=current_freq_data['individual_type'],
                                             calculated_mean=current_freq_data.get('calculated_mean', 'Arithmetic & Linear Mean'),
                                             sort=current_freq_data.get('sort', 'ascending'),
                                             return_fig=True,
                                             **self._binned_source_kwargs(current_freq_data))
                    elif current_freq_data['test_type'] in ('rpm_binned', 'pitch_binned_deg', 'pitch_binned_pct'):
                        result = plot_function(current_freq_data['bist'], save_figs=False,
                                             output_dir=self.output_dir,
                                             test_type='speed',
                                             param=current_freq_data['param'],
                                             param_unit=current_freq_data['param_unit'],
                                             param_adjust=current_freq_data['param_adjust'],
                                             param_lims=current_freq_data['param_lims'],
                                             binned_range_lims=current_freq_data['binned_range_lims'],
                                             error_bar_type=current_freq_data['error_bar_type'],
                                             individual_type=current_freq_data['individual_type'],
                                             calculated_mean=current_freq_data.get('calculated_mean', 'Arithmetic & Linear Mean'),
                                             sort=current_freq_data.get('sort', 'ascending'),
                                             return_fig=True,
                                             **self._binned_source_kwargs(current_freq_data))
                    elif current_freq_data.get('plot_type') == 'rx_noise':
                        result = read_bist.plot_rx_noise(
                            current_freq_data['bist'],
                            save_figs=False,
                            output_dir=self.output_dir,
                            test_type=self._rx_noise_plot_test_type(current_freq_data['test_type']),
                            param=current_freq_data.get('param', []),
                            param_unit=current_freq_data['param_unit'],
                            param_adjust=param_adjust,
                            param_lims=current_freq_data['param_lims'],
                            noise_lims=binned_range_lims,
                            cmap=current_freq_data.get('cmap', 'jet'),
                            sort=current_freq_data.get('sort', 'ascending'),
                            redblue_center=current_freq_data.get('redblue_center', 55),
                            return_fig=True,
                            gui_embed=True)
                    else:
                        # For other plot types, just regenerate with stored data
                        result = plot_function(**current_freq_data)
                    
                    # Check if we got a valid result
                    if result is not None:
                        # Handle tuple return (figure, data) - extract just the figure
                        if isinstance(result, tuple) and len(result) > 0:
                            figure = result[0]  # Extract the figure from the tuple
                            self.update_log(f"Extracted figure from tuple return: {type(figure)}")
                        else:
                            figure = result
                        
                        # Create a wrapper function that returns the figure
                        def plot_wrapper():
                            return figure
                        
                        # Display the regenerated plot
                        self.display_plot_in_window(plot_wrapper)
                        self.update_log("Plot regenerated with updated settings")
                    else:
                        self.update_log("Plot function returned None - regeneration failed")
                else:
                    self.update_log("No plot function found in frequency data")
        except Exception as e:
            self.update_log(f"Error regenerating plot: {e}")
            import traceback
            self.update_log(f"Traceback: {traceback.format_exc()}")

    def verify_system_info(self, warn=None):  # prompt user for missing fields or warn if different
        if warn is None:
            warn = self.warn_user_chk.isChecked()
        self.missing_fields = []
        self.conflicting_fields = []
        self.model_updated = False
        if not self._sn_user_entered:
            self.sn_updated = False
        self.date_updated = False
        if not self._freq_user_entered:
            self.freq_updated = False

        fnames_sel = [self.file_list.item(f).data(1) for f in range(self.file_list.count())
                      if self.file_list.item(f).isSelected()]

        if self.file_list.count() > 0 and warn:
            if not fnames_sel:  # prompt user to select files if none selected
                self.update_log('Please select BIST type and click Select BISTs to verify system info')
            else:
                self.update_log('Checking ' + str(len(fnames_sel)) + ' files for model, serial number, and date')

        for fname in fnames_sel:  # loop through files, verify BIST type, and plot if matches test type
            fname_str = fname[fname.rfind('/') + 1:].rstrip()
            # get SIS version for later use in parsers, store in BIST dict (BIST type verified at file selection)
            _, sis_ver_found = read_bist.verify_bist_type(fname)  # get SIS ver for RX Noise parser

            # get available system info in this file
            sys_info = read_bist.check_system_info(fname, sis_version=sis_ver_found)

            if not sys_info or any(not v for v in sys_info.values()):  # warn user if missing system info in file
                if sys_info:
                    missing_fields = ', '.join([k for k, v in sys_info.items() if not v])
                    self.update_log('***WARNINGS: Missing system info (' + missing_fields + ') in file ' + fname)
                else:
                    # self.update_log('***WARNING: Missing all system info in file ' + fname)
                    self.update_log('***WARNING: Missing all system info in file ' + fname_str)

                # continue

            # update user entry fields to any info available in BIST, store conflicting fields if different
            if sys_info['model'] and not self._model_user_entered:
                print('BIST has model=', sys_info['model'])
                model = sys_info['model']
                # if sys_info['model'].find('2040') > -1:
                if sys_info['model'] in ['2040', '2045', '2040P']:  # EM2040C MKII shows 'Sounder Type: 2045'
                    model = '2040'  # store full 2040 model name in sys_info, but just use 2040 for model comparison
                elif sys_info['model'] == '2042':
                    model = '2042'

                if not self.model_updated:  # update model with first model found
                    model_label = 'EM ' + model
                    if self.model_cbox.currentText() != model_label:
                        self.model_cbox.setCurrentIndex(self.model_cbox.findText(model_label))
                        self.update_log('Updated model to ' + self.model_cbox.currentText() + ' (first model found)')
                    self.model_updated = True

                # elif 'EM '+sys_info['model'] != self.model_cbox.currentText():  # model was updated but new model found
                elif 'EM '+model != self.model_cbox.currentText():  # model was updated but new model found

                    # self.update_log('***WARNING: New model (EM ' + sys_info['model'] + ') detected in ' + fname_str)
                    self.update_log('***WARNING: New model (EM ' + model + ') detected in ' + fname_str)
                    self.conflicting_fields.append('model')

            if sys_info['sn'] and not self._sn_user_entered:
                if not self.sn_updated:
                    sn_text = str(sys_info['sn']).strip()
                    if self.sn_tb.text().strip() != sn_text:
                        self._sn_programmatic_update = True
                        self.sn_tb.setText(sn_text)
                        self._sn_programmatic_update = False
                        self.update_log('Updated serial number to ' + self.sn_tb.text() + ' (first S/N found)')
                    self._sn_autofill_text = self.sn_tb.text().strip()

                    # SIS 5 only: explain PU- vs FN- prefix in activity log
                    if sis_ver_found == 5 and (str(sys_info['sn']).startswith('PU-') or str(sys_info['sn']).startswith('FN-')):
                        self.update_log('SIS 5 serial number: PU- = from PU serial line in file; FN- = from BIST header/filename')
                        if str(sys_info['sn']).startswith('FN-'):
                            self.update_log('***WARNING: FN- value may be last digits of IP (no PU serial in file); update if needed')
                            self.conflicting_fields.append('sn')

                    self.sn_updated = True

                elif sys_info['sn'] != self.sn_tb.text().strip():
                    self.update_log('***WARNING: New serial number (' + sys_info['sn'] + ') detected in ' + fname_str)
                    self.conflicting_fields.append('sn')

            if sys_info['date'] and not self._date_user_entered:
                if not self.date_updated:  # update date with first date found
                    date_text = str(sys_info['date']).strip()
                    if self.date_tb.text().strip() != date_text:
                        self._sysinfo_programmatic_update = True
                        self.date_tb.setText(date_text)
                        self._sysinfo_programmatic_update = False
                        self.update_log('Updated date to ' + self.date_tb.text() + ' (first date found)')
                    self._date_autofill_text = self.date_tb.text().strip()
                    self.date_updated = True

                elif sys_info['date'] != self.date_tb.text().strip():  # date was updated but new date found
                    self.update_log('***WARNING: New date (' + sys_info['date'] + ') detected in ' + fname_str)
                    self.conflicting_fields.append('date')

            if sys_info['model'] and not self._freq_user_entered:
                freq_model = sys_info['model']
                if freq_model in ['2040', '2045', '2040P']:
                    freq_model = '2040'
                freq_label = read_bist.get_freq(str(freq_model))
                if not self.freq_updated:
                    if self.freq_tb.text().strip() != freq_label:
                        self._sysinfo_programmatic_update = True
                        self.freq_tb.setText(freq_label)
                        self._sysinfo_programmatic_update = False
                        self.update_log('Updated frequency to ' + freq_label + ' (first frequency found)')
                    self._freq_autofill_text = self.freq_tb.text().strip()
                    self.freq_updated = True
                elif freq_label != self.freq_tb.text().strip():
                    self.update_log('***WARNING: New frequency (' + freq_label + ') detected in ' + fname_str)
                    self.conflicting_fields.append('frequency')

            # store missing fields, reduce to set after looping through files and disable/enable plot button
            self.missing_fields.extend([k for k in ['model', 'sn', 'date'] if not sys_info[k]])
            if not sys_info['model']:
                self.missing_fields.append('frequency')
            # print('self.missing fields =', self.missing_fields)
            # print('self.conflicting fields =', self.conflicting_fields)

        # after reading all files, reduce set of missing fields and disable/enable plot button accordingly
        self.missing_fields = [k for k in set(self.missing_fields)]
        self.conflicting_fields = [k for k in set(self.conflicting_fields)]
        confirmed = set()
        if self._model_user_entered:
            confirmed.add('model')
        if self._sn_user_entered:
            confirmed.add('sn')
        if self._date_user_entered:
            confirmed.add('date')
        if self._freq_user_entered:
            confirmed.add('frequency')
        if confirmed:
            self.missing_fields = [k for k in self.missing_fields if k not in confirmed]
            self.conflicting_fields = [k for k in self.conflicting_fields if k not in confirmed]

        # if self.missing_fields or self.conflicting_fields:
        self.update_sys_info_colors()
        if fnames_sel:
            self._sync_parsed_title_checkboxes()
        if warn and any(self.missing_fields or self.conflicting_fields):
            user_warning = QtWidgets.QMessageBox.question(self, 'System info check',
                'Red field(s) are either:\n\n' +
                '          1) not available from the selected BIST(s), or\n' +
                '          2) available but conflicting across selected BISTs\n\n' +
                'Please confirm these fields or update file selection before plotting.\n' +
                'System info shown will be used for any fields not found in a file, but will not replace fields parsed '
                'successfully (even if conflicting).',
                QtWidgets.QMessageBox.StandardButton.Ok)

    def update_sys_info_colors(self):  # update the user field colors to red/cyan based on missing/conflicting info
        confirmed = set()
        if self._model_user_entered:
            confirmed.add('model')
        if self._sn_user_entered:
            confirmed.add('sn')
        if self._date_user_entered:
            confirmed.add('date')
        if self._freq_user_entered:
            confirmed.add('frequency')
        for widget in [self.model_cbox, self.sn_tb, self.freq_tb, self.date_tb]:  # set text to red for all missing fields
            widget.setStyleSheet('color: cyan')  # reset field to cyan before checking missing/conflicting fields
            if widget.objectName() in confirmed:
                continue
            if widget.objectName() in self.missing_fields + self.conflicting_fields:
                widget.setStyleSheet('color: red')

    def plot_bist(self):
        # get list of selected files and send each to the appropriate plotter
        bist_test_type = self.type_cbox.currentText()
        self.update_log('Plotting selected ' + bist_test_type + ' BIST files')
        self.get_current_file_list()
        self._set_plot_selected_pending(False)
        self.refresh_system_info_from_ui()
        
        # Clear previous navigation state
        self.all_figures = []
        self.frequency_data = []
        self.current_chart_index = 0
        self.total_charts = 0
        self.freq_list = []  # Store chart names
        self.last_plotted_bist = None
        self.last_bist_test_type = None
        self.last_plotted_files = []
        self.last_into_seas_file = None
        self._clear_export_button_highlight()
        self._update_export_button()
        self.update_navigation_controls()
        
        # Update total tests for custom parameters if group box is enabled
        if self.custom_param_gb.isChecked():
            self.update_total_tests_from_selected_files()

        # housekeeping for updating each parsed BIST dict with system info (assume correct from user; add check later)
        freq = read_bist.get_freq(self.model_number)  # get nominal freq to use if not parsed
        swell_str = '_into_swell'  # identify the RX Noise/Spectrum file heading into the swell by '_into_swell.txt'
        # rxn_test_type = 1  # vs speed only for now; add selection, parsers, and plotters for heading tests later
        rxn_test_type = self.noise_test_type_cbox.currentIndex()
        print('rxn_test_type =', rxn_test_type)

        bist_count = 0  # reset
        bist_fail_list = []

        # set up dicts for parsed data; currently setup to work with read_bist with minimal modification as first step
        bist_list_index = self.bist_list.index(bist_test_type)
        bist = read_bist.init_bist_dict(bist_list_index)
        fnames_sel = [self.file_list.item(f).data(1) for f in range(self.file_list.count())
                      if self.file_list.item(f).isSelected()]

        if not fnames_sel:
            self.update_log('Please select at least one BIST to plot...')

        if self.type_cbox.currentIndex() == 2:  # check if RX Noise test
            if self.noise_test_type_cbox.currentIndex() in [0, 1, 2, 3, 4, 5, 6, 7, 8]:
                if self.custom_param_gb.isChecked():
                    self.update_log('RX Noise: Custom test parameters entered by user will override values parsed '
                                    'from files or filenames, and will be applied in order of files loaded')
                else:
                    noise_mode = self.noise_test_type_cbox.currentText()
                    if noise_mode == 'vs. RPM':
                        self.update_log('RX Noise vs. RPM: RPM values will be parsed from filename '
                                        '(or custom parameters), if available')
                    elif noise_mode == 'vs. RPM (Binned)':
                        self.update_log('RX Noise vs. RPM (Binned): RPM values will be parsed from filename, '
                                        'if available')
                    elif noise_mode == 'vs. Pitch (deg)':
                        self.update_log('RX Noise vs. Pitch (deg): Pitch values will be parsed from filename '
                                        '(or custom parameters), if available')
                    elif noise_mode == 'vs. Pitch (%)':
                        self.update_log('RX Noise vs. Pitch (%): Pitch values will be parsed from filename '
                                        '(or custom parameters), if available')
                    elif noise_mode in ('vs. Pitch (Binned) - deg', 'vs. Pitch (Binned) - %'):
                        self.update_log('RX Noise vs. Pitch (Binned): Pitch values will be parsed from filename '
                                        '(or custom parameters), if available')
                    else:
                        self.update_log('RX Noise vs. Speed: Speeds will be parsed from filename (SIS 4) or file '
                                        '(SIS 5), if available')
            else:  # check if azimuth test
                self.update_log('RX Noise vs. Azimuth: Ship heading will be parsed from the filename in the '
                                'format _123T.txt'' or _123.txt, if available.\n\n'
                                'Please right-click and select the file heading into the swell or enter the swell '
                                'direction manually (note: compass direction from which the seas are arriving).\n\n'
                                'Alternatively, swell direction may be included in the filename after the heading, '
                                'in the format _090S.  This is suitable for cases where the swell direction is not '
                                'consistent across all files, or simply to ensure it is logged explicitly for each.\n\n'
                                'For example, a BIST file on a true heading of 180 with swell out of the east would '
                                'have a filename ending with _180T_090S.txt')

                hdg_parsed = True
                az_parsed = True

                for fname in fnames_sel:  # loop through filenames and make sure at least the headings can be parsed
                    fname_str = fname[fname.rfind('/') + 1:].rstrip()
                    self.update_log('Checking heading/azimuth info in ' + fname_str)
                    print('checking heading/azimuth info in file ', fname_str)
                    temp_hdg, temp_az = self.parse_fname_hdg_az(fname_str)
                    print('back in loop, got temp_hdg and temp_az from parser: ', temp_hdg, temp_az)

                    if temp_hdg == '999':
                        print('failed to get HEADING from ', fname_str)
                        hdg_parsed = False

                    if temp_az == '999':
                        print('failed to get AZIMUTH from ', fname_str)
                        az_parsed = False

                if not hdg_parsed:
                    # warn user and return if headings are not included in filenames
                    self.update_swell_dir(hdg_parse_fail=True)
                    return

                if not az_parsed or self.swell_dir_tb.text() == self.swell_dir_default:
                    # warn user and return if the azimuth cannot be determined from current inputs
                    self.update_swell_dir(swell_parse_fail=True)
                    return

        for fname in fnames_sel:  # loop through files, verify BIST type, and plot if matches test type

            fname_str = fname[fname.rfind('/') + 1:].rstrip()
            self.update_log('Parsing ' + fname_str)
            # fname_str = fname[fname.rfind('/') + 1:].rstrip()

            # get SIS version for later use in parsers, store in BIST dict (BIST type verified at file selection)
            _, sis_ver_found = read_bist.verify_bist_type(fname)  # get SIS ver for RX Noise parser

            print('in BIST plotter, found SIS version:', sis_ver_found)

            # get available system info in this file
            sys_info = read_bist.check_system_info(fname, sis_version=sis_ver_found)
            print('sys_info return =', sys_info)

            bist_temp = []

            try:  # try parsing the files according to BIST type
                if bist_test_type == self.bist_list[1]:  # TX Channels
                    # print('\n****calling parse_tx_z from bist_plotter\n')
                    bist_temp = read_bist.parse_tx_z(fname, sis_version=sis_ver_found,
                                                                          cbox_model_num=self.model_number)
                    # print('********* after parse_tx_z, got bist_temp =', bist_temp)

                    # like RX Channels, some TX BISTs logged in SIS 4 follow the SIS 5 format; the SIS ver check
                    # returns 4 (correct) but parser returns empty bist_temp; retry with SIS 5 format as a last resort
                    # example: Australian Antarctic Division EM712 data recorded in SIS 4 (2022)
                    if not bist_temp and sys_info['model']:
                        if sys_info['model'] in ['712', '304', '124'] and sis_ver_found == 4:
                            print('bist_temp returned empty --> retrying parse_rx_noise with SIS 5 format')
                            bist_temp = read_bist.parse_tx_z(fname, sis_version=int(5))

                elif bist_test_type == self.bist_list[2]:  # RX Channels
                    # check model and skip EM2040 variants (model combobox is updated during verification step,
                    # so this can be checked even if model is not available in sys_info)
                    # print('sys info model is', sys_info['model'],' with type', type(sys_info['model']))

                    # skip 2040 (FUTURE: RX Channels for all freq)
                    # if sys_info['model']:
                    #     if sys_info['model'].find('2040') > -1:
                    #         self.update_log('***WARNING: RX Channels plot N/A for EM2040 variants: ' + fname_str)
                    #         bist_fail_list.append(fname)
                    #         continue

                    # if sys_info['model']:
                    #     if sys_info['model'].find('2040') > -1:
                    #         if sis_ver_found == 4:
                    #             self.update_log('***WARNING: RX Channels plot N/A for EM2040 (SIS 4): ' + fname_str)
                    #             bist_fail_list.append(fname)
                    #             continue

                    # elif self.model_cbox.currentText().find('2040') > -1:
                    #     self.update_log('***WARNING: Model not parsed from file and EM2040 selected; '
                    #                     'RX Channels plot not yet available for EM2040 variants: ' + fname_str)
                    #     bist_fail_list.append(fname)
                    #     continue

                    # elif self.model_cbox.currentText().find('2040') > -1:
                    #     if sis_ver_found == 4:
                    #         self.update_log('***WARNING: Model not parsed from file (EM2040 selected in system info); '
                    #                         'RX Channels plot not yet available for EM2040 (SIS 4) variants: ' + fname_str)
                    #         bist_fail_list.append(fname)
                    #         continue


                    print('*******calling parse_rx_z********** --> sis_ver_found =', sis_ver_found)
                    bist_temp = read_bist.parse_rx_z(fname, sis_version=sis_ver_found)

                    # some EM2040 RX Channels BISTs recorded in SIS 4 are in the SIS 5 format; retry if failed w/ SIS 4
                    if not bist_temp and sys_info['model']:
                        if sys_info['model'] in ['2040', '2045', '2040P', '712'] and sis_ver_found == 4:

                            print('retrying parse_rx_z for EM2040 / 2045(2040C) / 2040P / 712 with SIS 5 format')
                            bist_temp = read_bist.parse_rx_z(fname, sis_version=5, sis4_retry=True)


                elif bist_test_type == self.bist_list[3]:  # RX Noise
                    print('calling parse_rx_noise with sis_version =', sis_ver_found)
                    bist_temp = read_bist.parse_rx_noise(fname, sis_version=sis_ver_found)

                    # like RX Channels, some RX Noise BISTs logged in SIS 4 follow the SIS 5 format; the SIS ver check
                    # returns 4 (correct) but parser returns empty bist_temp; retry with SIS 5 format as a last resort
                    # example: Australian Antarctic Division EM712 data recorded in SIS 4 (2022)
                    if not bist_temp['rxn'] and sys_info['model']:
                        if sys_info['model'] in ['2040', '2045', '2040P', '712', '304', '124'] and sis_ver_found == 4:
                            print('bist_temp[rxn] returned empty --> retrying parse_rx_noise with SIS 5 format')
                            bist_temp = read_bist.parse_rx_noise(fname, sis_version=int(5))

                    # print('in main script, BIST_temp[test]=', bist_temp['test'])
                    # print('with type', type(bist_temp['test']))
                    # print('with size', np.size(bist_temp['test']))
                    # print('and len', len(bist_temp['test']))

                    # get speed or heading of test from filename
                    if rxn_test_type in [0, 1, 2, 3, 4, 5, 6, 7, 8]:  # speed, binned, RPM/pitch heatmap, RPM/pitch binned; parse param from fname

                        print('\n\n****got bist_temp[speed] =', bist_temp['speed'])

                        # if bist_temp['speed'] == []:  # try to get speed from filename if not parsed from BIST
                        # try to get speed from filename if SOG was not parsed (e.g., SIS 4) OR if test is not for SOG
                        # if bist_temp['speed'] == [] or self.prm_unit_cbox.currentText().lower().find('sog') == -1:
                        if bist_temp['speed'] == [] or self.ignore_sis5_speeds_chk.isChecked() or \
                            self.prm_unit_cbox.currentText().split()[0].lower() not in ['sog', 'stw']:

                            print('getting bist_temp[speed_bist] from the filename for test units: ', self.prm_unit_cbox.currentText())

                            # self.update_log('Parsing speeds from SIS 4 filenames (e.g., "_6_kts.txt", "_9p5_kts.txt")')
                            try:
                                temp_speed = float(999.9)  # placeholder speed

                                if not self.custom_param_gb.isChecked():
                                    # continue trying to get speed from filename if custom speed is not checked
                                    temp = ["".join(x) for _, x in itertools.groupby(self.prm_str_tb.text(), key=str.isdigit)]
                                    print('********parsing speed based on example prm_str = ', self.prm_str_tb.text())
                                    print('temp =', temp)
                                    print('DEBUG: Filename being parsed:', fname)
                                    print('DEBUG: Parameter string from GUI:', self.prm_str_tb.text())
                                    print('DEBUG: Parameter unit selected:', self.prm_unit_cbox.currentText())

                                    # take all characters between first and last elements in temp, if not digits
                                    print('temp[-1].isdigit() is', temp[-1].isdigit())
                                    print('DEBUG: temp[-1] =', repr(temp[-1]))
                                    if not temp[-1].isdigit():
                                        print('trying to split at non-digit char following speed')
                                        print('DEBUG: Looking for non-digit char:', repr(temp[-1]), 'in filename:', fname)
                                        try:
                                            temp_speed = fname.rsplit(temp[-1], 1)[0]  # split at non-digit char following speed
                                            print('splitting fname at non-digit char following speed: temp_speed=', temp_speed)
                                        except:
                                            print('***failed to split at non-digit char following speed')
                                    else:
                                        print('trying to split at decimal')
                                        temp_speed = fname.rsplit(".", 1)[0]  # or split at start of file extension
                                        print('splitting fname temp speed at file ext: temp_speed=', temp_speed)

                                    print('after first step, temp_speed=', temp_speed)

                                    print('temp[0].isdigit() is', temp[0].isdigit())
                                    print('DEBUG: temp[0] =', repr(temp[0]))
                                    if not temp[0].isdigit():
                                        print('trying to split at non-digit char preceding speed')
                                        print('DEBUG: Looking for non-digit char:', repr(temp[0]), 'in temp_speed:', temp_speed)
                                        temp_speed = temp_speed.rsplit(temp[0], 1)[-1]  # split at non-digit char preceding spd
                                        print('DEBUG: After splitting at non-digit char, temp_speed =', temp_speed)
                                    else:
                                        print('splitting at last _ preceding speed')
                                        print('DEBUG: Before splitting at _, temp_speed =', temp_speed)
                                        # temp_speed = temp_speed.rsplit("_", 1)[-1]  # or split at last _ or / preceding speed
                                        temp_speed = temp_speed.rsplit('_', 1)[-1].rsplit('/', 1)[-1]
                                        print('DEBUG: After splitting at _, temp_speed =', temp_speed)

                                    print('after second step, temp_speed=', temp_speed)
                                    print('DEBUG: Before final conversion, temp_speed type:', type(temp_speed), 'value:', repr(temp_speed))
                                    temp_speed = float(temp_speed.replace(" ", "").replace("p", "."))  # replace
                                    print('DEBUG: After final conversion, temp_speed =', temp_speed, 'type:', type(temp_speed))

                                bist_temp['speed'] = temp_speed  # store updated speed if

                                # testing to assign one speed per test rather than one speed per file
                                print('after parsing, bist_temp[test]=', bist_temp['test'])
                                bist_temp['speed_bist'] = [temp_speed for i in range(len(bist_temp['test']))]
                                print('bist_temp[speed_bist] =', bist_temp['speed_bist'])

                            except ValueError:
                                self.update_log('***WARNING: Error parsing speeds from filenames; '
                                                'check filename string example if parsing test parameter from filename,'
                                                'or use custom test parameters')
                                self.update_log('***SIS v4 RX Noise file names must include speed, '
                                                '.e.g., "_6_kts.txt" or "_9p5_kts.txt"')
                                bist_fail_list.append(fname)
                                continue

                    elif rxn_test_type == 9:  # RX noise vs azimuth rel to seas; get hdg, swell dir from fname or user
                        if bist_temp['hdg_true'] == [] and bist_temp['azimuth'] == []:
                            try:
                                self.update_log('Parsing headings (and azimuths, if available) from filenames')

                                temp_hdg, temp_az = self.parse_fname_hdg_az(fname_str)

                                bist_temp['hdg_true'] = float(temp_hdg)
                                bist_temp['azimuth'] = float(temp_az)
                                bist_temp['azimuth_bist'] = [float(temp_az) for i in range(len(bist_temp['test']))]

                                print('got hdgs ', bist_temp['hdg_true'], bist_temp['azimuth'], 'in ', fname_str)
                                print('bist_temp[azimuth_bist] =', bist_temp['azimuth_bist'])
                                # self.update_log('Assigning date (' + bist_temp['date'] + ') from filename')
                                # try:
                                    # if fname_str.find(swell_str) > -1:
                                    #     bist_temp['file_idx_into_swell'] = bist_count
                                    # get heading from fname "..._hdg_010.txt" or "...hdg_055_into_swell.txt"
                                    # bist_temp['hdg'] = float(fname.replace(swell_str, '').rsplit("_")[-1].rsplit(".")[0])


                            except ValueError:
                                self.update_log('***WARNING: Error parsing headings from filenames; default format to '
                                                'include is, e.g., "_045T_000S.txt" where T indicates the true heading '
                                                '(e.g., 000T = North) and S indicates the heading relative to seas on '
                                                'the bow (e.g., 000S = into the seas, 045S = seas on port bow, 090S = '
                                                'seas on port side, etc.)\n'
                                                'If headings relative to the seas are not known (or not relevant), '
                                                'the true heading for each file may be included using the same format '
                                                '(e.g., "_045T.txt") and heading relative to the seas may be excluded.')
                                bist_fail_list.append(fname)
                                continue

                # elif bist_test_type == self.bist_list[4]:  # RX Spectrum
                #     bist_temp = read_bist.parseRXSpectrum(fname)  # SPECTRUM PARSER NOT WRITTEN

                else:
                    print("Unknown test type: ", bist_test_type)

                if bist_temp == []:
                    # self.update_log('***WARNING: No data parsed in ' + fname)
                    self.update_log('***WARNING: No data parsed in ' + fname_str)
                    bist_fail_list.append(fname)
                    continue  # do not try to append

            except ValueError:
                self.update_log('***WARNING: Error parsing ' + fname)
                bist_fail_list.append(fname)
                pass  # do not try to append

            else:  # try to append data if no exception during parsing
                # print('no exceptions during parsing, checking bist_temp for file', fname_str)
                try:
                    # add user fields if not parsed from BIST file (availability depends on model and SIS ver)
                    # this can be made more elegant once all modes are working
                    # print('*********** ----> checking info, at start of attempt to append bist_temp to full bist dict:')
                    # print('bist_temp[frequency]=', bist_temp['frequency'])
                    # print('bist_temp[model]=', bist_temp['model'])
                    # print('bist_temp[sn]=', bist_temp['sn'])
                    # print('bist_temp[date]=', bist_temp['date'])
                    # print('bist_temp[time]=', bist_temp['time'])

                    print('bist_temp[frequency] has type = ')
                    # if bist_temp['frequency'] == []:  # add freq if empty (e.g., most SIS 4 BISTs); np array if read
                    # if not bist_temp['frequency']:  # this doesn't work for checking numpy arrays
                    if np.size(bist_temp['frequency']) == 0:  # update for Python 3.10 - old check for [] doesn't work
                        print('bist_temp[frequency] is empty, adding freq')
                        bist_temp['frequency'] = [[freq]]  # add freq as list to match format of parsed multi-freq
                        print('added bist_temp[frequency] = ', bist_temp['frequency'])
                    else:
                        print('bist_temp[frequency] is populated')

                    print('checking bist_temp[date]')
                    if not bist_temp['date']:  # add date if not parsed (incl. in SIS 5, but not all SIS 4 or TX chan)
                        print('bist_temp[date] not found, trying to get from other sources')
                        self.update_log('***WARNING: no date parsed from file ' + fname_str)

                        if sys_info['date']:  # take date from sys_info if parsed
                            bist_temp['date'] = sys_info['date']

                        else:  # otherwise, try to get from filename or take from user input
                            print('trying to get date from filename format guesses')
                            try:
                                try:
                                    date_guess = re.search(r"\d{8}", fname_str).group()

                                except:
                                    date_guess = re.search(r"\d{4}[-_]\d{2}[-_]\d{2}", fname_str).group()

                                bist_temp['date'] = date_guess.replace("_", "").replace("-","")

                                self.update_log('Assigning date (' + bist_temp['date'] + ') from YYYYMMDD in filename')

                            except:
                                if self.date_str.replace('/', '').isdigit():  # user date if modified from yyyy/mm/dd
                                    date_str = self.date_str.split()
                                    bist_temp['date'] = self.date_str.replace('/','')
                                    self.update_log('Assigning date (' + bist_temp['date'] + ') from user input')

                        if bist_temp['date'] == []:
                            self.update_log('***WARNING: no date assigned to ' + fname_str + '\n' +
                                            '           This file may be skipped if date/time are required\n' +
                                            '           Update filenames to include YYYYMMDD (or enter date ' +
                                            'in user input field if all files are on the same day)')

                    if not bist_temp['time']:  # add time if not parsed (incl. in SIS 5, but not all SIS 4 or TX chan)
                        print('bist_temp[time] not found, trying to get from other sources')
                        self.update_log('***WARNING: no time parsed from test information in file ' + fname_str)

                        if sys_info['time']:  # take date from sys_info if parsed
                            bist_temp['time'] = sys_info['time']
                            self.update_log('Assigning time (' + bist_temp['time'] + ') from system info')

                        else:  # otherwise, try to get from filename or take from user input
                            print('*** no sis_info[time]--> trying to get time from filename')
                            try:  # assume date and time in filename are YYYYMMDD and HHMMSS with _ or - in between
                                print('try start')
                                # print('fname_str =', fname_str)
                                # time_str = re.search(r"[_-]\d{6}", fname_str).group()
                                # time_str = re.search(r"_?-?\d{6}_?-?\d{6}", fname_str).group()
                                # print('got time_str =', time_str)
                                # bist_temp['time'] = time_str.replace('_', "").replace('-', "")
                                # bist_temp['time'] = time_str.replace('_', "").replace('-', "")[-6:]

                                # take last six digits in filename as the time
                                # this fails with other numbers (e.g., speed) in the file name
                                # time_str = ''.join([c for c in fname_str if c.isnumeric()])

                                # testing more flexible fname time parsing (exclude numbers without - or _, e.g., 12kt

                                if bist_temp['date']:  # split filename after date if available
                                    print('bist_temp[date] is available')
                                    fname_str_split = fname_str.split(bist_temp['date'])[1]
                                    print('got fname_str_split =', fname_str_split)

                                    try:  # try parsing 4 or 6 digit time separated by _- or space from rest of fname
                                        print('trying regex search for 4- or 6-digit time_str in filename')
                                        time_str_temp = re.search(r"[ _-](\d{4}|\d{6})[ _-]", fname_str_split).group()
                                        print('found time_str_temp: ', time_str_temp)

                                        # remove delimiters, pad with zeros as necessary, and add .000
                                        time_str_temp = time_str_temp[1:-1].ljust(6, '0') + '.000'
                                        print('got time_str_temp = ', time_str_temp)

                                    except:
                                        print('did not find 4- or 6-digit time_str after date_str in fname_str_split')
                                        time_str_temp = '000000.000'

                                    if time_str_temp > '240000.000':
                                        print('parsed time_str_temp greater than 240000.000; replacing with 000000.000')
                                        time_str_temp = '000000.000'

                                # date_str = re.search("\d{8}", fname_str).group()
                                # time_str = date_str + time_str_temp

                                print('storing bist_temp[time] = ', time_str_temp)
                                bist_temp['time'] = time_str_temp

                                print('final date and time are ', bist_temp['date'], bist_temp['time'])

                                time_str = bist_temp['date'] + bist_temp['time']
                                time_str = time_str.split('.')[0]

                                if len(time_str) == 14:
                                    self.update_log('Assigning time (' + bist_temp['time'] + ') from filename')

                                else:
                                    self.update_log('***WARNING: date and time not parsed (expected YYYYMMDD HHMM[SS] '
                                                    'format, separated by - or _ from the rest of the filename, e.g., '
                                                    'BIST_file_20210409_123000.txt); assigning time 000000.000 for '
                                                    'this file')
                                    bist_temp['time'] = '000000.000'  # placeholder time

                                self.update_log('Assigned date / time: ' + bist_temp['date'] + '/' + bist_temp['time'])

                            except:
                                self.update_log('***WARNING: no time assigned to ' + fname_str + '\n' +
                                                '           This file may be skipped if date/time are required\n' +
                                                '           Update filenames to include time, e.g., YYYYMMDD-HHMMSS')

                    if bist_temp['model'] == []:  # add model if not parsed
                        print('bist_temp[model] not found, trying to get from other sources')

                        if sys_info['model']:
                            bist_temp['model'] = sys_info['model']
                        else:
                            bist_temp['model'] = self.model_number

                    if bist_temp['sn'] == []:  # add serial number if not parsed
                        print('bist_temp[sn] not found, trying to get from other sources')
                        if sys_info['sn'] and sis_ver_found != 5:
                            bist_temp['sn'] = sys_info['sn']  # add serial number if not parsed from system info
                        else:  # store user-entered serial number if not available or possible SIS 5 bug
                            bist_temp['sn'] = self.sn

                    print('************ after checking, bist_temp info is now:')
                    print('bist_temp[frequency]=', bist_temp['frequency'])
                    print('bist_temp[model]=', bist_temp['model'])
                    print('bist_temp[sn]=', bist_temp['sn'])
                    print('bist_temp[date]=', bist_temp['date'])

                    # store other fields
                    bist_temp['sis_version'] = sis_ver_found  # store SIS version
                    bist_temp['ship_name'] = self._optional_sysinfo_text(self.ship_tb)
                    bist_temp['cruise_name'] = self._optional_sysinfo_text(self.cruise_tb)

                    # append dicts
                    print('starting to append bist_temp dict')
                    bist = read_bist.appendDict(bist, bist_temp)
                    bist_count += 1  # increment counter if no issues parsing or appending
                    print('done appending bist_temp dict; total bist_count is now ', bist_count)

                except ValueError:
                    # self.update_log('***WARNING: Error appending ' + fname)
                    print('WARNING: error appending ' + fname_str)
                    self.update_log('***WARNING: Error appending ' + fname_str)
                    bist_fail_list.append(fname)

        if bist['filename']:  # try plotting only if at least one BIST was parsed successfully
            if len(bist_fail_list) > 0:
                self.update_log('The following BISTs will not be plotted:')
                for i in range(len(bist_fail_list)):
                    self.update_log('     ' + str(i + 1) + ". " + bist_fail_list[i])

            self.update_log('Plotting ' + str(bist_count) + ' ' + self.type_cbox.currentText() + ' BIST files...')
            self.verify_system_info(warn=False)
            self._apply_sn_title_metadata(bist)
            self.last_plotted_bist = bist
            self.last_bist_test_type = bist_test_type
            failed = {str(f).replace('\\', '/') for f in bist_fail_list}
            self.last_plotted_files = [f.replace('\\', '/') for f in fnames_sel
                                       if f.replace('\\', '/') not in failed]
            self.last_into_seas_file = None
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                path = (item.data(1) or '').replace('\\', '/')
                if self.file_into_seas_str in item.text() and path in self.last_plotted_files:
                    self.last_into_seas_file = path
                    break

            if bist_test_type == self.bist_list[1]:  # TX Channels
                history_only = self._channel_history_only()
                self.last_channel_plot_style = 'History' if history_only else 'Plot All'
                # Initialize navigation for TX channel plots
                self.all_figures = []
                self.frequency_data = []
                self.freq_list = []  # Store chart names
                self.total_charts = 0
                self.current_chart_index = 0
                
                # Generate TX channel plots for each file and plot style
                if not history_only:
                    for i in range(len(bist['filename'])):
                        for ps in [1, 2]:  # loop through both available styles of TX Z plots
                            try:
                                # Store the data needed to regenerate this plot
                                plot_data = {
                                    'bist': bist,
                                    'file_index': i,
                                    'plot_style': ps,
                                    'plot_type': 'tx_channels'
                                }
                                self.frequency_data.append(plot_data)

                                # Generate the plot and get the figure
                                figure = self.generate_tx_channel_plot(bist, file_index=i, plot_style=ps,
                                                                      save_figs=False, output_dir=self.output_dir)
                                if figure:
                                    self.all_figures.append(figure)
                                    self.total_charts += 1

                                    # Create a descriptive name for this plot
                                    fname_str = bist['filename'][i][bist['filename'][i].rfind("/") + 1:-4]
                                    plot_name = f"TX Channels - {fname_str} (Style {ps})"
                                    self.freq_list.append(plot_name)

                            except Exception as e:
                                self.update_log(f"Error generating TX channel plot for file {i}, style {ps}: {str(e)}")
                                continue

                # Add TX history plot to GUI navigation as the third TX plot type
                try:
                    history_plot_data = {
                        'bist': bist,
                        'plot_type': 'tx_channels',
                        'plot_subtype': 'history'
                    }
                    self.frequency_data.append(history_plot_data)
                    tx_history_figure = read_bist.plot_tx_z_history(
                        bist,
                        save_figs=False,
                        output_dir=self.output_dir,
                        return_fig=True,
                        gui_mode=True
                    )
                    if tx_history_figure:
                        self.all_figures.append(tx_history_figure)
                        self.total_charts += 1
                        model = bist['model'][0] if bist['model'] else "Unknown"
                        sn = bist['sn'][0] if bist['sn'] else "Unknown"
                        self.freq_list.append(f"TX Channels History - EM{model} SN {sn}")
                except Exception as e:
                    self.update_log(f"Error generating TX history plot: {str(e)}")
                
                # Display the first TX channel plot in GUI
                if self.all_figures:
                    self.display_current_frequency()
                    self.update_navigation_controls()
                    self.update_log(f"Generated {len(self.all_figures)} TX channel plots. Use navigation buttons to cycle through them.")
                else:
                    self.update_log("No TX channel plots were generated successfully.")
                self._update_export_button(mark_pending=True)

            elif bist_test_type == self.bist_list[2]:  # RX Channels
                history_only = self._channel_history_only()
                self.last_channel_plot_style = 'History' if history_only else 'Plot All'
                # Initialize navigation for RX channel plots
                self.all_figures = []
                self.frequency_data = []
                self.freq_list = []  # Store chart names
                self.total_charts = 0
                self.current_chart_index = 0
                
                # Generate RX channel plots for GUI display - need to handle multiple frequencies
                try:
                    # Get the number of frequencies to generate plots for
                    file_index = 0  # Use first file
                    test_index = list(bist['rx'][file_index].keys())[0]  # Use first test
                    n_freq = len(bist['freq_range'][file_index][test_index])
                    
                    self.update_log(f"Generating RX channel plots for {n_freq} frequencies...")
                    
                    fname_str = bist['filename'][0][bist['filename'][0].rfind("/") + 1:-4]
                    freq_labels = [str(f) for f in bist['freq_range'][file_index][test_index]]
                    
                    # Heatmap and line+heatmap are one pair per test, then the next test.
                    if not history_only:
                        heatmap_figure = read_bist.plot_rx_z(bist, save_figs=False, output_dir=self.output_dir, return_fig=True, gui_mode=True)
                        lineheat_figure = read_bist.plot_rx_z_line_heatmap(
                            bist,
                            save_figs=False,
                            output_dir=self.output_dir,
                            return_fig=True,
                            gui_mode=True
                        )
                        self._append_rx_channel_plots_by_test(
                            heatmap_figure, lineheat_figure, bist, fname_str, freq_labels)

                    # Generate the history plot using plot_rx_z_history
                    history_figure = read_bist.plot_rx_z_history(bist, save_figs=False, output_dir=self.output_dir, return_fig=True, gui_mode=True)
                    self._append_rx_channel_plot_results(
                        history_figure, bist, 'history', fname_str, freq_labels)
                        
                except Exception as e:
                    self.update_log(f"Error generating RX channel plots: {str(e)}")
                    import traceback
                    self.update_log(f"Traceback: {traceback.format_exc()}")
                
                # Display the RX channel plots in GUI
                if self.all_figures:
                    self.display_current_frequency()
                    self.update_navigation_controls()
                    self.update_log(f"Generated {len(self.all_figures)} RX channel plots. Use navigation buttons to cycle through them.")
                else:
                    self.update_log("No RX channel plots were generated successfully.")
                self._update_export_button(mark_pending=True)

            elif bist_test_type == self.bist_list[3]:  # RX Noise
                self._active_transient_threshold = self._transient_threshold_db()
                self._remember_transient_filter_applied()
                freq_list = bist['frequency'][0][0]  # freq list; assume identical across all files
                # print('freq_list=', freq_list)
                # print('bist=', bist)

                # if rxn_test_type == 0:
                # Map dropdown index to test_type, handling the new binned options
                dropdown_index = self.noise_test_type_cbox.currentIndex()
                if dropdown_index == 0:  # vs. Speed
                    test_type = 'speed'
                elif dropdown_index == 1:  # vs. Speed (Binned) - 1kt
                    test_type = 'speed_binned'
                elif dropdown_index == 2:  # vs. Speed (Binned) - 2kt
                    test_type = 'speed_binned_2kt'
                elif dropdown_index == 3:  # vs. RPM
                    test_type = 'rpm'
                elif dropdown_index == 4:  # vs. RPM (Binned)
                    test_type = 'rpm_binned'
                elif dropdown_index == 5:  # vs. Pitch (deg)
                    test_type = 'pitch_deg'
                elif dropdown_index == 6:  # vs. Pitch (Binned) - deg
                    test_type = 'pitch_binned_deg'
                elif dropdown_index == 7:  # vs. Pitch (%)
                    test_type = 'pitch_pct'
                elif dropdown_index == 8:  # vs. Pitch (Binned) - %
                    test_type = 'pitch_binned_pct'
                elif dropdown_index == 9:  # vs. Azimuth
                    test_type = 'azimuth'
                else:
                    test_type = 'speed'  # fallback
                param_unit = self.prm_unit_cbox.currentText()
                param_adjust = 0.0
                sort_order = self.sort_cbox.currentText().lower().strip()

                # sort_by = test_type
                print('test_type = ', test_type)

                param_list = []
                param_lims = []

                if self.prm_plot_lim_gb.isChecked():
                    param_lims = [float(self.prm_plot_min_tb.text()), float(self.prm_plot_max_tb.text())]

                if self.custom_param_gb.isChecked():
                    # apply param list from custom entries; assumes BISTs are loaded and selected in order of
                    # increasing param corresponding to these custom params; there is no other way to check!
                    self.update_param_info()
                    param_list = np.repeat(self.param_list, int(self.num_tests_tb.text()))
                    param_count = len(bist['test'])  # Use actual number of test files, not parameter count
                    print('using custom param list=', param_list)

                elif test_type in ('speed', 'rpm', 'pitch_deg', 'pitch_pct', 'speed_binned', 'speed_binned_2kt',
                                   'rpm_binned', 'pitch_binned_deg', 'pitch_binned_pct'):
                    # param_list = bist['speed_bist']
                    param_count = len(bist['speed'])

                    if 'stw' in self.prm_unit_cbox.currentText().lower():  # get current magnitude and relative scale
                        print('***getting current value for Speed Through Water adjustment****')
                        param_adjust = float(self.current_tb.text())
                        param_adjust *= float([-1 if 'with' in self.current_dir_cbox.currentText().lower() else 1][0])
                        print('***STW test ---> applying param adjust =', param_adjust)

                elif test_type == 'azimuth':
                #     param_list = bist['azimuth_bist']
                    param_count = len(bist['azimuth'])

                print('*****ahead of plotting, bist[speed]=', bist['speed'])
                print('*****ahead of plotting, bist[speed_bist]=', bist['speed_bist'])
                print('*****ahead of plotting, bist[azimuth]=', bist['azimuth'])
                print('*****ahead of plotting, bist[azimuth_bist]=', bist['azimuth_bist'])

                # Handle binned plotting separately
                if test_type == 'speed_binned':
                    self.update_log('Generating binned RX noise plot (1kt bins)...')
                    # For binned plots, we need to use 'speed' as the test_type for the plotting function
                    plot_test_type = 'speed'
                    
                    binned_range_lims = self._rx_noise_range_lims()
                    
                    # Handle multiple frequencies for binned plotting (same logic as regular plotting)
                    if len(set(freq_list)) == 1:
                        print('single frequency found in binned RX Noise test')
                        bist['frequency'] = [freq_list]  # simplify single frequency, assuming same across all tests
                        
                        # Initialize navigation for single chart
                        self.all_figures = []
                        self.frequency_data = []
                        self.freq_list = freq_list
                        self.total_charts = 1
                        self.current_chart_index = 0
                        
                        # Generate the single frequency plot
                        try:
                            # Store the data needed to regenerate this plot
                            plot_data = {
                                'bist': bist,
                                'test_type': 'speed_binned',
                                'plot_type': 'rx_noise_binned',  # Add consistent plot_type key
                                'param': param_list,
                                'param_unit': self.prm_unit_cbox.currentText(),
                                'param_adjust': param_adjust,
                                'param_lims': param_lims,
                                'binned_range_lims': binned_range_lims,
                                'error_bar_type': self.binned_error_type_cb.currentText(),
                                'individual_type': self.binned_individual_cb.currentText(),
                                'calculated_mean': self._binned_calculated_mean(),
                                'sort': sort_order,
                                'plot_function': read_bist.plot_rx_noise_binned_new,  # Store function for regeneration
                                'model': self.model_number,
                                'sn': self.sn,
                                'ship_name': self.ship_name,
                                'description': self.cruise_name,
                                'date': self.date_str
                            }
                            base_name = str(freq_list[0]) if freq_list else 'Binned'
                            self.freq_list = self._emit_rx_noise_charts(
                                bist, param_list, plot_data, base_name,
                                lambda bist_i, param_i: read_bist.plot_rx_noise_binned_new(
                                    bist_i, save_figs=False,
                                    output_dir=self.output_dir,
                                    test_type=plot_test_type,
                                    param=param_i,
                                    param_unit=self.prm_unit_cbox.currentText(),
                                    param_adjust=param_adjust,
                                    param_lims=param_lims,
                                    binned_range_lims=binned_range_lims,
                                    error_bar_type=self.binned_error_type_cb.currentText(),
                                    individual_type=self.binned_individual_cb.currentText(),
                                    calculated_mean=self._binned_calculated_mean(),
                                    sort=sort_order,
                                    return_fig=True),
                                source_fn=read_bist.plot_rx_noise_binned_new)
                            self.total_charts = len(self.all_figures)
                            if not self.all_figures:
                                self.update_log('No binned RX noise plot was created')
                                return
                            
                            # Display the plot in GUI
                            self.display_current_frequency()
                            self.update_navigation_controls()
                            
                        except Exception as e:
                            self.update_log(f'Error generating binned plot: {str(e)}')
                            return
                    else:  # multiple frequencies - use navigation system
                        print('multiple frequencies found in binned RX Noise test, setting up navigation')
                        
                        # Initialize navigation for multiple charts
                        self.all_figures = []
                        self.frequency_data = []
                        self.freq_list = freq_list
                        self.total_charts = len(freq_list)
                        self.current_chart_index = 0
                        chart_names = []
                        
                        # Generate plots for each frequency
                        for f in range(len(freq_list)):
                            print('f=', f)
                            bist_freq = copy.deepcopy(bist)  # copy, pare down columns for each frequency
                            print('bist_freq=', bist_freq)
                            bist_freq['rxn'] = []

                            for p in range(param_count):
                                for t in bist['test'][p]:
                                    # print('working on f=', f, ' p =', p, ' and t = ', t)
                                    rxn_array_z = [np.array(bist['rxn'][p][t][:, f])]
                                    bist_freq['rxn'].append(rxn_array_z)  # store in frequency-specific BIST dict
                                    bist_freq['frequency'] = [[freq_list[f]]]  # plotter expects list of freq

                            try:
                                # Store the data needed to regenerate this plot
                                plot_data = {
                                    'bist': bist_freq,
                                    'test_type': 'speed_binned',
                                    'plot_type': 'rx_noise_binned',  # Add consistent plot_type key
                                    'param': param_list,
                                    'param_unit': self.prm_unit_cbox.currentText(),
                                    'param_adjust': param_adjust,
                                    'param_lims': param_lims,
                                    'binned_range_lims': binned_range_lims,
                                    'sort': sort_order,
                                    'error_bar_type': self.binned_error_type_cb.currentText(),
                                    'individual_type': self.binned_individual_cb.currentText(),
                                    'calculated_mean': self._binned_calculated_mean(),
                                    'plot_function': read_bist.plot_rx_noise_binned_new,
                                }
                                chart_names.extend(self._emit_rx_noise_charts(
                                    bist_freq, param_list, plot_data, str(freq_list[f]),
                                    lambda bist_i, param_i: read_bist.plot_rx_noise_binned_new(
                                        bist_i, save_figs=False,
                                        output_dir=self.output_dir,
                                        test_type=plot_test_type,
                                        param=param_i,
                                        param_unit=self.prm_unit_cbox.currentText(),
                                        param_adjust=param_adjust,
                                        param_lims=param_lims,
                                        binned_range_lims=binned_range_lims,
                                        error_bar_type=self.binned_error_type_cb.currentText(),
                                        individual_type=self.binned_individual_cb.currentText(),
                                    calculated_mean=self._binned_calculated_mean(),
                                        sort=sort_order,
                                        return_fig=True),
                                    source_fn=read_bist.plot_rx_noise_binned_new))
                                
                            except Exception as e:
                                self.update_log(f'Error generating binned plot for frequency {f}: {str(e)}')
                                continue

                        self.freq_list = chart_names
                        self.total_charts = len(self.all_figures)
                        
                        # Display the first frequency plot in GUI
                        if self.frequency_data:
                            self.display_current_frequency()
                            self.update_navigation_controls()
                        else:
                            self.update_log('No valid binned plots generated')
                            return
                elif test_type == 'speed_binned_2kt':
                    self.update_log('Generating binned RX noise plot (2kt bins)...')
                    # For 2kt binned plots, we need to use 'speed' as the test_type for the plotting function
                    plot_test_type = 'speed'
                    
                    binned_range_lims = self._rx_noise_range_lims()
                    
                    # Handle multiple frequencies for 2kt binned plotting (same logic as regular plotting)
                    if len(set(freq_list)) == 1:
                        print('single frequency found in 2kt binned RX Noise test')
                        bist['frequency'] = [freq_list]  # simplify single frequency, assuming same across all tests
                        
                        # Initialize navigation for single chart
                        self.all_figures = []
                        self.frequency_data = []
                        self.freq_list = freq_list
                        self.total_charts = 1
                        self.current_chart_index = 0
                        
                        # Generate the single frequency plot
                        try:
                            # Store the data needed to regenerate this plot
                            plot_data = {
                                'bist': bist,
                                'test_type': 'speed_binned_2kt',
                                'plot_type': 'rx_noise_binned',  # Add consistent plot_type key
                                'param': param_list,
                                'param_unit': self.prm_unit_cbox.currentText(),
                                'param_adjust': param_adjust,
                                'param_lims': param_lims,
                                'binned_range_lims': binned_range_lims,
                                'error_bar_type': self.binned_error_type_cb.currentText(),
                                'individual_type': self.binned_individual_cb.currentText(),
                                'calculated_mean': self._binned_calculated_mean(),
                                'sort': sort_order,
                                'plot_function': read_bist.plot_rx_noise_binned_2kt,  # Store function for regeneration
                                'model': self.model_number,
                                'sn': self.sn,
                                'ship_name': self.ship_name,
                                'description': self.cruise_name,
                                'date': self.date_str
                            }
                            base_name = str(freq_list[0]) if freq_list else 'Binned'
                            self.freq_list = self._emit_rx_noise_charts(
                                bist, param_list, plot_data, base_name,
                                lambda bist_i, param_i: read_bist.plot_rx_noise_binned_2kt(
                                    bist_i, save_figs=False,
                                    output_dir=self.output_dir,
                                    test_type=plot_test_type,
                                    param=param_i,
                                    param_unit=self.prm_unit_cbox.currentText(),
                                    param_adjust=param_adjust,
                                    param_lims=param_lims,
                                    binned_range_lims=binned_range_lims,
                                    error_bar_type=self.binned_error_type_cb.currentText(),
                                    individual_type=self.binned_individual_cb.currentText(),
                                    calculated_mean=self._binned_calculated_mean(),
                                    sort=sort_order,
                                    return_fig=True),
                                source_fn=read_bist.plot_rx_noise_binned_2kt)
                            self.total_charts = len(self.all_figures)
                            if not self.all_figures:
                                self.update_log('No 2kt binned RX noise plot was created')
                                return
                            
                            # Display the plot in GUI
                            self.display_current_frequency()
                            self.update_navigation_controls()
                            
                        except Exception as e:
                            self.update_log(f'Error generating 2kt binned plot: {str(e)}')
                            return
                    else:  # multiple frequencies - use navigation system
                        print('multiple frequencies found in 2kt binned RX Noise test, setting up navigation')
                        
                        # Initialize navigation for multiple charts
                        self.all_figures = []
                        self.frequency_data = []
                        self.freq_list = freq_list
                        self.total_charts = len(freq_list)
                        self.current_chart_index = 0
                        chart_names = []
                        
                        # Generate plots for each frequency
                        for f in range(len(freq_list)):
                            print('f=', f)
                            bist_freq = copy.deepcopy(bist)  # copy, pare down columns for each frequency
                            print('bist_freq=', bist_freq)
                            bist_freq['rxn'] = []

                            for p in range(param_count):
                                for t in bist['test'][p]:
                                    print('working on f=', f, ' p =', p, ' and t = ', t)
                                    rxn_array_z = [np.array(bist['rxn'][p][t][:, f])]
                                    bist_freq['rxn'].append(rxn_array_z)  # store in frequency-specific BIST dict
                                    bist_freq['frequency'] = [[freq_list[f]]]  # plotter expects list of freq

                            try:
                                # Store the data needed to regenerate this plot
                                plot_data = {
                                    'bist': bist_freq,
                                    'test_type': 'speed_binned_2kt',
                                    'plot_type': 'rx_noise_binned',  # Add consistent plot_type key
                                    'param': param_list,
                                    'param_unit': self.prm_unit_cbox.currentText(),
                                    'param_adjust': param_adjust,
                                    'param_lims': param_lims,
                                    'binned_range_lims': binned_range_lims,
                                    'sort': sort_order,
                                    'error_bar_type': self.binned_error_type_cb.currentText(),
                                    'individual_type': self.binned_individual_cb.currentText(),
                                    'calculated_mean': self._binned_calculated_mean(),
                                    'plot_function': read_bist.plot_rx_noise_binned_2kt,
                                }
                                chart_names.extend(self._emit_rx_noise_charts(
                                    bist_freq, param_list, plot_data, str(freq_list[f]),
                                    lambda bist_i, param_i: read_bist.plot_rx_noise_binned_2kt(
                                        bist_i, save_figs=False,
                                        output_dir=self.output_dir,
                                        test_type=plot_test_type,
                                        param=param_i,
                                        param_unit=self.prm_unit_cbox.currentText(),
                                        param_adjust=param_adjust,
                                        param_lims=param_lims,
                                        binned_range_lims=binned_range_lims,
                                        error_bar_type=self.binned_error_type_cb.currentText(),
                                        individual_type=self.binned_individual_cb.currentText(),
                                    calculated_mean=self._binned_calculated_mean(),
                                        sort=sort_order,
                                        return_fig=True),
                                    source_fn=read_bist.plot_rx_noise_binned_2kt))
                                
                            except Exception as e:
                                self.update_log(f'Error generating 2kt binned plot for frequency {f}: {str(e)}')
                                continue

                        self.freq_list = chart_names
                        self.total_charts = len(self.all_figures)
                        
                        # Display the first frequency plot in GUI
                        if self.frequency_data:
                            self.display_current_frequency()
                            self.update_navigation_controls()
                        else:
                            self.update_log('No valid 2kt binned plots generated')
                            return
                elif test_type in ('rpm_binned', 'pitch_binned_deg', 'pitch_binned_pct'):
                    if test_type == 'rpm_binned':
                        discrete_plot_fn = read_bist.plot_rx_noise_binned_rpm
                        discrete_label = 'RPM'
                    else:
                        discrete_plot_fn = read_bist.plot_rx_noise_binned_pitch
                        discrete_label = 'Pitch'
                    self.update_log(f'Generating binned RX noise plot ({discrete_label} bins)...')
                    plot_test_type = 'speed'
                    
                    binned_range_lims = self._rx_noise_range_lims()
                    
                    # Handle multiple frequencies for discrete binned plotting (same logic as regular plotting)
                    if len(set(freq_list)) == 1:
                        print(f'single frequency found in {discrete_label} binned RX Noise test')
                        bist['frequency'] = [freq_list]  # simplify single frequency, assuming same across all tests
                        
                        # Initialize navigation for single chart
                        self.all_figures = []
                        self.frequency_data = []
                        self.freq_list = freq_list
                        self.total_charts = 1
                        self.current_chart_index = 0
                        
                        # Generate the single frequency plot
                        try:
                            # Store the data needed to regenerate this plot
                            plot_data = {
                                'bist': bist,
                                'test_type': test_type,
                                'plot_type': 'rx_noise_binned',  # Add consistent plot_type key
                                'param': param_list,
                                'param_unit': self.prm_unit_cbox.currentText(),
                                'param_adjust': param_adjust,
                                'param_lims': param_lims,
                                'binned_range_lims': binned_range_lims,
                                'error_bar_type': self.binned_error_type_cb.currentText(),
                                'individual_type': self.binned_individual_cb.currentText(),
                                'calculated_mean': self._binned_calculated_mean(),
                                'sort': sort_order,
                                'plot_function': discrete_plot_fn,
                                'model': self.model_number,
                                'sn': self.sn,
                                'ship_name': self.ship_name,
                                'description': self.cruise_name,
                                'date': self.date_str
                            }
                            base_name = str(freq_list[0]) if freq_list else 'Binned'
                            self.freq_list = self._emit_rx_noise_charts(
                                bist, param_list, plot_data, base_name,
                                lambda bist_i, param_i, plot_fn=discrete_plot_fn: plot_fn(
                                    bist_i, save_figs=False,
                                    output_dir=self.output_dir,
                                    test_type=plot_test_type,
                                    param=param_i,
                                    param_unit=self.prm_unit_cbox.currentText(),
                                    param_adjust=param_adjust,
                                    param_lims=param_lims,
                                    binned_range_lims=binned_range_lims,
                                    error_bar_type=self.binned_error_type_cb.currentText(),
                                    individual_type=self.binned_individual_cb.currentText(),
                                    calculated_mean=self._binned_calculated_mean(),
                                    sort=sort_order,
                                    return_fig=True),
                                source_fn=discrete_plot_fn)
                            self.total_charts = len(self.all_figures)
                            if not self.all_figures:
                                self.update_log(f'No {discrete_label} binned RX noise plot was created')
                                return
                            
                            # Display the plot in GUI
                            self.display_current_frequency()
                            self.update_navigation_controls()
                            
                        except Exception as e:
                            self.update_log(f'Error generating {discrete_label} binned plot: {str(e)}')
                            return
                    else:
                        # Multiple frequencies - generate separate plots for each frequency
                        print(f'multiple frequencies found in {discrete_label} binned RX Noise test')
                        
                        # Initialize navigation for multiple charts
                        self.all_figures = []
                        self.frequency_data = []
                        self.freq_list = freq_list
                        self.total_charts = len(freq_list)
                        self.current_chart_index = 0
                        chart_names = []
                        
                        # Generate plots for each frequency
                        for f in freq_list:
                            try:
                                # Create frequency-specific BIST data
                                bist_freq = {}
                                for key in bist:
                                    if key in ['rx', 'rx_array', 'freq_range', 'test_datetime', 'rx_limits', 'rx_array_limits', 'rx_units']:
                                        # These keys contain frequency-specific data
                                        if isinstance(bist[key], list):
                                            bist_freq[key] = [bist[key][freq_list.index(f)]]
                                        else:
                                            bist_freq[key] = [bist[key]]
                                    else:
                                        # These keys are the same for all frequencies
                                        bist_freq[key] = bist[key]
                                
                                # Store the data needed to regenerate this plot
                                plot_data = {
                                    'bist': bist_freq,
                                    'test_type': test_type,
                                    'plot_type': 'rx_noise_binned',  # Add consistent plot_type key
                                    'param': param_list,
                                    'param_unit': self.prm_unit_cbox.currentText(),
                                    'param_adjust': param_adjust,
                                    'param_lims': param_lims,
                                    'binned_range_lims': binned_range_lims,
                                    'error_bar_type': self.binned_error_type_cb.currentText(),
                                    'individual_type': self.binned_individual_cb.currentText(),
                                    'calculated_mean': self._binned_calculated_mean(),
                                    'sort': sort_order,
                                    'plot_function': discrete_plot_fn,
                                    'model': self.model_number,
                                    'sn': self.sn,
                                    'ship_name': self.ship_name,
                                    'description': self.cruise_name,
                                    'date': self.date_str
                                }
                                chart_names.extend(self._emit_rx_noise_charts(
                                    bist_freq, param_list, plot_data, str(f),
                                    lambda bist_i, param_i, plot_fn=discrete_plot_fn: plot_fn(
                                        bist_i, save_figs=False,
                                        output_dir=self.output_dir,
                                        test_type=plot_test_type,
                                        param=param_i,
                                        param_unit=self.prm_unit_cbox.currentText(),
                                        param_adjust=param_adjust,
                                        param_lims=param_lims,
                                        binned_range_lims=binned_range_lims,
                                        error_bar_type=self.binned_error_type_cb.currentText(),
                                        individual_type=self.binned_individual_cb.currentText(),
                                    calculated_mean=self._binned_calculated_mean(),
                                        sort=sort_order,
                                        return_fig=True),
                                    source_fn=discrete_plot_fn))
                                
                            except Exception as e:
                                self.update_log(f'Error generating {discrete_label} binned plot for frequency {f}: {str(e)}')
                                continue

                        self.freq_list = chart_names
                        self.total_charts = len(self.all_figures)
                        
                        # Display the first frequency plot in GUI
                        if self.frequency_data:
                            self.display_current_frequency()
                            self.update_navigation_controls()
                        else:
                            self.update_log(f'No valid {discrete_label} binned plots generated')
                            return
                else:
                    # Regular plotting (not binned). Empty range keeps the 30-70 dB color ramp.
                    noise_lims = self._rx_noise_range_lims()
                    if len(set(freq_list)) == 1:
                    # if len(set((bist['frequency'][0][0]))) == 1:  # single frequency detected, single plot
                        print('single frequency found in RX Noise test')
                        bist['frequency'] = [freq_list]  # simplify single frequency, assuming same across all tests
                        
                        # Initialize navigation for single chart
                        self.all_figures = []
                        self.frequency_data = []
                        self.freq_list = freq_list
                        self.total_charts = 1
                        self.current_chart_index = 0
                        
                        # Generate the single frequency plot
                        try:
                            # Store the data needed to regenerate this plot
                            plot_data = {
                                'bist': bist,
                                'test_type': test_type,
                                'plot_type': 'rx_noise',
                                'plot_function': read_bist.plot_rx_noise,
                                'param': param_list,
                                'param_unit': self.prm_unit_cbox.currentText(),
                                'param_adjust': param_adjust,
                                'param_lims': param_lims,
                                'noise_lims': noise_lims,
                                'cmap': self.cmap_cbox.currentText().lower().strip(),
                                'sort': self.sort_cbox.currentText().lower().strip(),
                                'redblue_center': self.redblue_center_spin.value()
                            }
                            base_name = str(freq_list[0]) if freq_list else 'RX Noise'
                            self.freq_list = self._emit_rx_noise_charts(
                                bist, param_list, plot_data, base_name,
                                lambda bist_i, param_i: read_bist.plot_rx_noise(
                                    bist_i, save_figs=False,
                                    output_dir=self.output_dir,
                                    test_type=self._rx_noise_plot_test_type(test_type),
                                    param=param_i,
                                    param_unit=self.prm_unit_cbox.currentText(),
                                    param_adjust=param_adjust,
                                    param_lims=param_lims,
                                    noise_lims=noise_lims,
                                    cmap=self.cmap_cbox.currentText().lower().strip(),
                                    sort=self.sort_cbox.currentText().lower().strip(),
                                    redblue_center=self.redblue_center_spin.value(),
                                    return_fig=True,
                                    gui_embed=True))
                            self.total_charts = len(self.all_figures)
                            if not self.all_figures:
                                self.update_log('No RX noise plot was created')
                                return

                            # Display the plot and set up navigation
                            self.display_current_frequency()
                            self.update_navigation_controls()
                            self.update_log(f"Generated {len(self.all_figures)} chart(s) for {freq_list[0]}")
                        except Exception as e:
                            self.update_log(f"Error generating single chart: {str(e)}")

                    else:  # loop through each frequency, reduce RXN data for each freq and call plotter for that subset
                        print('multiple frequencies found in RX Noise test, setting up to plot each freq')
                        
                        # Initialize storage for all frequency plots
                        self.all_figures = []
                        self.frequency_data = []
                        self.freq_list = []
                        self.total_charts = 0
                        self.current_chart_index = 0
                        chart_names = []
                        
                        for f in range(len(freq_list)):
                            print('f=', f)
                            bist_freq = copy.deepcopy(bist)  # copy, pare down columns for each frequency
                            print('bist_freq=', bist_freq)
                            bist_freq['rxn'] = []

                            for p in range(param_count):
                                # print('before trying to grab freqs, size of bist[rxn][p] =', np.shape(bist['rxn'][p]))
                                # print('bist[test][p] =', bist['test'][p])
                                for t in bist['test'][p]:
                                    print('working on f=', f, ' p =', p, ' and t = ', t)
                                    rxn_array_z = [np.array(bist['rxn'][p][t][:, f])]
                                    bist_freq['rxn'].append(rxn_array_z)  # store in frequency-specific BIST dict
                                    bist_freq['frequency'] = [[freq_list[f]]]  # plotter expects list of freq

                            # print('\n\n*********for f = ', f, 'and bist_freq =', bist_freq)
                            # print('calling plot_rx_noise with param_list = ', param_list)
                            # print('bist_freq[speed_bist]=', bist_freq['speed_bist'])
                            # print('bist_freq[azimuth_bist]=', bist_freq['azimuth_bist'])
                            # print('bist-freq[rxn] has shape', np.shape(bist_freq['rxn']))

                            # Generate plot for this frequency and store the figure
                            try:
                                # Store the data needed to regenerate this plot
                                plot_data = {
                                    'bist': bist_freq,
                                    'test_type': test_type,
                                    'plot_type': 'rx_noise',
                                    'plot_function': read_bist.plot_rx_noise,
                                    'param': param_list,
                                    'param_unit': param_unit,
                                    'param_adjust': param_adjust,
                                    'param_lims': param_lims,
                                    'noise_lims': noise_lims,
                                    'cmap': self.cmap_cbox.currentText().lower().strip(),
                                    'sort': self.sort_cbox.currentText().lower().strip(),
                                    'redblue_center': self.redblue_center_spin.value()
                                }
                                names = self._emit_rx_noise_charts(
                                    bist_freq, param_list, plot_data, str(freq_list[f]),
                                    lambda bist_i, param_i: read_bist.plot_rx_noise(
                                        bist_i, save_figs=False,
                                        output_dir=self.output_dir,
                                        test_type=self._rx_noise_plot_test_type(test_type),
                                        param=param_i,
                                        param_unit=param_unit,
                                        param_adjust=param_adjust,
                                        param_lims=param_lims,
                                        noise_lims=noise_lims,
                                        cmap=self.cmap_cbox.currentText().lower().strip(),
                                        sort=self.sort_cbox.currentText().lower().strip(),
                                        redblue_center=self.redblue_center_spin.value(),
                                        return_fig=True,
                                        gui_embed=True))
                                chart_names.extend(names)
                                self.update_log(f"Generated {len(names)} chart(s) for frequency {freq_list[f]}")
                            except Exception as e:
                                self.update_log(f"Error generating chart for frequency {freq_list[f]}: {str(e)}")
                                # Create a placeholder figure if plotting fails
                                placeholder_fig = plt.figure(figsize=(8, 6))
                                plt.text(0.5, 0.5, f'Error plotting chart for frequency {freq_list[f]}', 
                                        ha='center', va='center', transform=plt.gca().transAxes)
                                self.all_figures.append(placeholder_fig)
                                chart_names.append(str(freq_list[f]))
                        self.freq_list = chart_names
                        self.total_charts = len(self.all_figures)
                        
                        # Display the first frequency plot and set up navigation
                        if self.all_figures:
                            self.display_current_frequency()
                            self.update_navigation_controls()
                            self.update_log(f"Generated {len(self.all_figures)} frequency plots. Use navigation buttons to cycle through them.")
                        else:
                            self.update_log("No frequency plots were generated successfully.")

                self._update_export_button(mark_pending=True)

            elif bist_test_type == self.bist_list[4]:  # RX Spectrum
                print('RX Spectrum parser and plotter are not available yet...')

        else:
            self.update_log('No BISTs to plot')

    def update_log(self, entry):  # update the activity log
        self.log.append(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' ' + entry)
        QtWidgets.QApplication.processEvents()

    def update_prog(self, total_prog):
        self.calc_pb.setValue(total_prog)
        QtWidgets.QApplication.processEvents()

    def _is_rx_noise_level_figure(self, figure, plot_type=None, test_type=None):
        """True for RX Noise Level heatmaps (speed/azimuth/etc.), not binned line plots."""
        if plot_type == 'rx_noise':
            return True
        if plot_type and str(plot_type).startswith('rx_noise_binned'):
            return False
        if test_type in ('speed', 'azimuth', 'rpm', 'pitch_deg', 'pitch_pct'):
            return True
        if figure is None:
            return False
        # Heuristic: Level plot uses 3 GridSpec rows (param, heatmap, colorbar)
        return len(figure.get_axes()) >= 3 and bool(figure.get_suptitle())

    def _show_figure_on_canvas(self, figure, plot_type=None, test_type=None):
        """Bind a figure to the Qt canvas and size it to the plot window (GUI only).

        Exports call plot functions separately with save_figs=True, so this does not
        change exported figure size/layout.
        """
        if figure is None:
            return

        self._show_plot_canvas()

        # Drop the temporary pyplot/Qt canvas created by plt.figure()
        old_canvas = getattr(figure, 'canvas', None)
        figure.set_canvas(self.plot_figure_canvas)
        self.plot_figure_canvas.figure = figure
        self.plot_figure = figure
        if old_canvas is not None and old_canvas is not self.plot_figure_canvas:
            try:
                old_canvas.close()
            except Exception:
                pass

        self._plot_show_meta = {'plot_type': plot_type, 'test_type': test_type}
        self._sync_canvas_figure_size(figure, plot_type=plot_type, test_type=test_type)

        # Re-sync after Qt finishes layout (fixes first paint at export 8x11 aspect)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._resync_shown_figure_size)

    def _sync_canvas_figure_size(self, figure, plot_type=None, test_type=None):
        """Match figure inches to the canvas widget using matplotlib's resize path."""
        if figure is None or self.plot_figure_canvas.figure is not figure:
            return

        QtWidgets.QApplication.processEvents()
        size = self.plot_figure_canvas.size()
        if size.width() < 50 or size.height() < 50:
            parent = self.plot_figure_canvas.parentWidget()
            if parent is not None and parent.width() > 50 and parent.height() > 50:
                size = parent.size()
            else:
                size = QSize(max(size.width(), 400), max(size.height(), 400))

        self.plot_figure_canvas.resizeEvent(QtGui.QResizeEvent(size, size))

        if self._is_rx_noise_level_figure(figure, plot_type=plot_type, test_type=test_type):
            # Keep GridSpec margins from plot_rx_noise; only leave room for the title
            try:
                figure.subplots_adjust(top=0.88)
            except Exception:
                pass
        elif plot_type == 'tx_channels' and getattr(figure, '_bist_tx_style', None) == 2:
            # Window resize keeps the tall-page spacing, which puts the line plot
            # on top of the heatmap's upper tick labels and axis title.
            self._layout_tx_style2_onscreen(figure)
        elif plot_type == 'tx_channels':
            try:
                read_bist._center_axes_block_in_figure(figure, top_margin=0.88)
            except Exception:
                pass
        elif plot_type == 'rx_channels':
            # Keep the bottom margin from the RX plot, then pull a clipped heatmap Y label back up.
            for ax in figure.axes:
                if ax.get_ylabel():
                    read_bist._raise_ylabel_inside_figure(figure, ax)
        elif figure.get_suptitle():
            try:
                figure.tight_layout(rect=[0, 0, 1, 0.93])
            except Exception:
                pass

        self.plot_figure_canvas.updateGeometry()

    def _layout_tx_style2_onscreen(self, figure):
        """Keep the TX line plot clear of the heatmap title and top labels."""
        try:
            figure.tight_layout(rect=[0, 0, 1, 0.84], pad=0.6, h_pad=2.6)
        except Exception:
            try:
                figure.subplots_adjust(top=0.84, bottom=0.08, hspace=0.75)
            except Exception:
                pass

    def _resync_shown_figure_size(self):
        meta = getattr(self, '_plot_show_meta', None) or {}
        figure = getattr(self, 'plot_figure', None)
        if figure is None:
            return
        self._sync_canvas_figure_size(
            figure,
            plot_type=meta.get('plot_type'),
            test_type=meta.get('test_type'))
        self.plot_figure_canvas.draw_idle()

    def display_plot_in_window(self, plot_function, *args, **kwargs):
        """Display a plot in the GUI plot window"""
        try:
            self.update_log(f"Starting display_plot_in_window for {plot_function.__name__}")
            
            # Clear the previous plot
            self.plot_figure.clear()
            
            # Create the plot using the provided function
            result = plot_function(*args, **kwargs)
            
            self.update_log(f"Plot function returned: {type(result)}")
            
            # Check what the function returned
            if hasattr(result, 'get_axes'):
                self.update_log(f"Result is a figure with {len(result.get_axes())} axes")
                # It's a figure object (like from plot_rx_noise)
                # Try to use the returned figure directly
                try:
                    # Replace our figure with the returned one
                    self._show_figure_on_canvas(result)
                    self.update_log(
                        f"Fitted figure to canvas: {self.plot_figure.get_size_inches()}")
                    
                    self.update_log("Successfully replaced figure with returned figure")
                    
                    # Ensure the colorbar is properly displayed
                    # The colorbar should already be part of the returned figure
                    # but we need to make sure it's visible in the canvas
                    self.plot_figure_canvas.draw()
                    self.plot_figure_canvas.flush_events()
                    QtWidgets.QApplication.processEvents()
                    self.update_log("Canvas updated with colorbar")
                except Exception as e:
                    self.update_log(f"Failed to replace figure directly: {e}")
                    # Fall back to copying approach
                    # Reset to better figure size and try again
                    try:
                        self._show_figure_on_canvas(self.plot_figure)
                        self.plot_figure_canvas.draw()
                        self.update_log("Canvas updated after size adjustment")
                    except Exception as e2:
                        self.update_log(f"Failed to adjust figure size: {e2}")
                        # Continue with fallback copying approach
                    self.plot_figure.clear()
                    
                    # Get the axes from the returned figure
                    returned_axes = result.get_axes()
                    if len(returned_axes) > 0:
                        # Handle multiple subplots (like RX noise plots)
                        if len(returned_axes) > 1:
                            self.update_log(f"Handling {len(returned_axes)} subplots")
                            # Create subplots with the same layout as the original
                            from matplotlib import gridspec
                            gs = gridspec.GridSpec(2, 1, height_ratios=[1, 4], 
                                                  right=0.969, bottom=0.064)  # 0.25 inches from right edge, 0.7 inches from bottom edge
                            
                            # Copy each subplot
                            for i, ax in enumerate(returned_axes):
                                if i == 0:
                                    new_ax = self.plot_figure.add_subplot(gs[0])
                                else:
                                    new_ax = self.plot_figure.add_subplot(gs[1])
                                
                                # Copy the plot content
                                if hasattr(ax, 'get_xlim'):
                                    new_ax.set_xlim(ax.get_xlim())
                                    new_ax.set_ylim(ax.get_ylim())
                                
                                # Copy the plot data if it's an image plot
                                if hasattr(ax, 'get_images') and len(ax.get_images()) > 0:
                                    img = ax.get_images()[0]
                                    img_array = img.get_array()
                                    img_cmap = img.get_cmap()
                                    img_clim = img.get_clim()
                                    self.update_log(f"Image data shape: {img_array.shape}, cmap: {img_cmap}, clim: {img_clim}")
                                    # Simple imshow without extra parameters
                                    new_ax.imshow(img_array, cmap=img_cmap, 
                                                  vmin=img_clim[0], vmax=img_clim[1])
                                    new_ax.invert_yaxis()
                                    self.update_log(f"Copied image plot for subplot {i}")
                                
                                # Copy the plot data if it's a line plot
                                if len(ax.get_lines()) > 0:
                                    for line in ax.get_lines():
                                        new_ax.plot(line.get_xdata(), line.get_ydata(), 
                                                  color=line.get_color(), marker=line.get_marker())
                                    self.update_log(f"Copied {len(ax.get_lines())} line plots for subplot {i}")
                                
                                # Copy title and labels
                                if ax.get_title():
                                    new_ax.set_title(ax.get_title())
                                if ax.get_xlabel():
                                    new_ax.set_xlabel(ax.get_xlabel())
                                if ax.get_ylabel():
                                    new_ax.set_ylabel(ax.get_ylabel())
                                
                                # Copy ticks and grid
                                new_ax.set_xticks(ax.get_xticks())
                                new_ax.set_yticks(ax.get_yticks())
                                new_ax.set_xticklabels(ax.get_xticklabels())
                                new_ax.set_yticklabels(ax.get_yticklabels())
                                # Grid disabled due to matplotlib API issues
                            
                            # Copy the figure title if it exists
                            if result.get_suptitle():
                                self.plot_figure.suptitle(result.get_suptitle())
                        
                        else:
                            self.update_log("Handling single subplot")
                            # Single subplot
                            ax = returned_axes[0]
                            new_ax = self.plot_figure.add_subplot(111)
                            
                            # Copy the plot content
                            if hasattr(ax, 'get_xlim'):
                                new_ax.set_xlim(ax.get_xlim())
                                new_ax.set_ylim(ax.get_ylim())
                            if ax.get_legend():
                                new_ax.legend()
                            
                            # Copy the plot data if it's an image plot
                            if hasattr(ax, 'get_images') and len(ax.get_images()) > 0:
                                img = ax.get_images()[0]
                            new_ax.imshow(img.get_array(), cmap=img.get_cmap(), 
                                         vmin=img.get_clim()[0], vmax=img.get_clim()[1])
                            new_ax.invert_yaxis()
                            self.update_log("Copied image plot")
                        
                        # Copy the plot data if it's a line plot
                        if len(ax.get_lines()) > 0:
                            for line in ax.get_lines():
                                new_ax.plot(line.get_xdata(), line.get_ydata(), 
                                          color=line.get_color(), marker=line.get_marker())
                            self.update_log(f"Copied {len(ax.get_lines())} line plots")
                        
                        # Copy title and labels
                        if ax.get_title():
                            new_ax.set_title(ax.get_title())
                        if ax.get_xlabel():
                            new_ax.set_xlabel(ax.get_xlabel())
                        if ax.get_ylabel():
                            new_ax.set_ylabel(ax.get_ylabel())
                        
                        # Copy ticks and grid
                        new_ax.set_xticks(ax.get_xticks())
                        new_ax.set_yticks(ax.get_yticks())
                        new_ax.set_xticklabels(ax.get_xticklabels())
                        new_ax.set_yticklabels(ax.get_yticklabels())
                        # Grid disabled due to matplotlib API issues
                
            elif result is not None and hasattr(result, 'get_geometry'):
                self.update_log("Result is a subplot")
                # It's a subplot, get its position
                pos = result.get_geometry()
                new_ax = self.plot_figure.add_subplot(pos[0], pos[1], pos[2])
            elif result is not None and hasattr(result, 'get_xlim'):
                self.update_log("Result is a single axes")
                # It's a single axes, create a new one
                new_ax = self.plot_figure.add_subplot(111)
                
                # Copy the plot content
                new_ax.set_xlim(result.get_xlim())
                new_ax.set_ylim(result.get_ylim())
                if result.get_legend():
                    new_ax.legend()
            else:
                self.update_log("Function doesn't return useful data, showing message")
                # Function doesn't return anything useful, create a simple plot
                new_ax = self.plot_figure.add_subplot(111)
                new_ax.text(0.5, 0.5, 'Plot generated successfully\nCheck output directory for saved file', 
                           ha='center', va='center', transform=new_ax.transAxes, fontsize=12)
                new_ax.set_xlim(0, 1)
                new_ax.set_ylim(0, 1)
            
            # Update the canvas with a slight delay to ensure all elements are drawn
            try:
                self.plot_figure_canvas.draw_idle()
                self.plot_figure_canvas.flush_events()
                # Force a small delay to ensure the canvas updates properly
                QtWidgets.QApplication.processEvents()
                # Trigger a resize event to force complete redraw
                self.plot_figure_canvas.resizeEvent(None)
            except Exception as e:
                self.update_log(f"Warning: Could not update canvas: {e}")
            
            read_bist.attach_rx_noise_speed_hover(self.plot_figure, self.plot_figure_canvas)
            read_bist.attach_rx_channel_hover(self.plot_figure, self.plot_figure_canvas)
            read_bist.attach_tx_channel_hover(self.plot_figure, self.plot_figure_canvas)
            self.update_log(f"Plot displayed in GUI window successfully")
            
        except Exception as e:
            self.update_log(f"Error displaying plot: {str(e)}")
            import traceback
            self.update_log(f"Traceback: {traceback.format_exc()}")
    
    def update_param_info(self):
        try:
            prm_min = float(self.prm_min_tb.text())
            prm_max = float(self.prm_max_tb.text())
            prm_int = float(self.prm_int_tb.text())
            prm_num = np.floor((prm_max-prm_min)/prm_int) + 1
            print('min, max, int, num=', prm_min, prm_max, prm_int, prm_num)
            self.param_list = np.arange(0, prm_num)*prm_int + prm_min
            self.param_list.round(decimals=1)
            print('param_list=', self.param_list)
            # self.total_num_params_tb.setText(str(np.size(self.param_list)))
            self.total_num_tests_tb.setText(str(int(prm_num*float(self.num_tests_tb.text()))))
            self.final_params_lbl.setText(self.final_params_hdr +
                                          np.array2string(self.param_list, precision=1, separator=', '))
            # self.final_params_lbl.setText(self.final_params_hdr + ', '.join([p for p in self.param_list]))

        except:
            pass

    def parse_fname_hdg_az(self, fname_str='fname_str_000T_000S.txt'):
        # parse ship heading and swell direction from a file name, if available
        # heading is required as 3-digit string w/ or w/o T (denoting 'true'), e.g., '_090T.txt'
        # swell dir is optional after hdg as 3-digit string w/ or w/o S (denoting 'swell'), e.g. '_090T_270S.txt'
        temp_hdg = '999'
        temp_az = '999'
        temp_swell = '999'

        try:  # try parsing file name
            try:  # try to parse ship heading and swell direction (e.g., '_045T_270S.txt' or '_045_270.txt)
                hdgs = re.search(r"[_]\d{1,3}[T]?[_]\d{1,3}[S]?(_|.txt)", fname_str).group().split('_')[1:]
                temp_hdg = ''.join([c for c in hdgs[0] if c.isdigit()])
                temp_swell = ''.join([c for c in hdgs[1] if c.isdigit()])
                print('found hdgs with format _045[T]_000[S], hdgs = ', hdgs)
                self.update_log('Parsed true heading and swell direction from ' + fname_str)
                self.swell_dir_tb.setText(temp_swell)
                self.update_log('Parsed swell direction ' + self.swell_dir_tb.text() + ' deg from filename')
                self.swell_dir_updated = True

            except:  # look for simple heading (e.g., _234T.txt), get swell direction from user
                hdgs = re.search(r"[_]\d{1,3}[T]?(_|.txt)", fname_str).group().split('_')[1:]
                temp_hdg = ''.join([c for c in hdgs[0] if c.isdigit()])
                print('found hdgs with format _123[T], hdgs = ', hdgs, ' getting swell from input')
                self.update_log('Parsed true heading (no swell direction) from ' + fname_str)
                temp_swell = self.swell_dir_tb.text()

            temp_az = str(np.mod(float(temp_hdg) - float(temp_swell), 360))  # get azimuth re swell dir on [0,360]
            print('got temp_hdg = ', temp_hdg, ' and temp_az =', temp_az)

        except:
            self.update_log('Failed to parse heading/swell direction from ' + fname_str)

        return temp_hdg, temp_az

    def update_swell_dir(self, swell_parse_fail=False, hdg_parse_fail=False):
        # get the swell direction for RX Noise vs Azimuth tests, if not found from filenames
        self.tabs.setCurrentIndex(2)  # show noise test params tab

        swell_dir_text = ('RX noise vs. azimuth processing requires user input to specify the ship heading and '
                          'direction of the prevailing seas.\n\n' \
                          'HEADING must be specified in each file name as a three-digit true heading in the format '
                          '_123T.txt or _123.txt.\n\n' \
                          'SWELL DIRECTION must be specified by one of the following options:\n\n' \
                          'Option 1: Right-click the file heading into the seas and select Set file INTO SEAS\n\n' \
                          'Option 2: Enter the swell direction manually under Noise Test --> Swell direction\n\n' \
                          'Option 3: Include the swell direction in the file name as a three-digit direction ' \
                          '(after ship heading) in the format _060S.txt or _060.txt.  For instance, the file name for '
                          'a BIST recorded on a heading of 270 with swell from the east would end in _270T_090S.txt\n\n'
                          'Options 1 and 2 are suitable for steady swell direction and option 3 is suitable if swell '
                          'direction changes throughout the files (e.g., BISTs recorded over several hours.\n\n' \
                          'Note that swell direction is the compass direction from which the swell is arriving; for ' \
                          'example, swell out of the northwest is 270 and swell out of the northeast is 045.')

        if swell_parse_fail:  # add a note if plot attempt failed to get swell direction
            self.swell_dir_updated = False
            swell_dir_text = 'WARNING: Swell direction was not found.\n\n' + swell_dir_text

        if hdg_parse_fail:  # add a note if plot attempt failed to get heading
            swell_dir_text = 'WARNING: Heading was not found.\n\n' + swell_dir_text

        if self.swell_dir_tb.text() == self.swell_dir_default or not self.swell_dir_updated:
            swell_dir_warning = QtWidgets.QMessageBox.question(self, 'RX Noise vs. Azimuth (relative to seas)',
                                                           swell_dir_text, QtWidgets.QMessageBox.StandardButton.Ok)
            self.swell_dir_message = False

        else:
            self.swell_dir_updated = True

    def eventFilter(self, source, event):
        # Select the unset marker so the next keystroke replaces it
        if (event.type() == QEvent.Type.FocusIn and source in (self.ship_tb, self.cruise_tb)
                and source.text().strip() == '?'):
            QTimer.singleShot(0, source.selectAll)

        # enable user to right-click and set a file "INTO SEAS" for the noise vs azimuth test
        if (event.type() == QEvent.Type.ContextMenu and source is self.file_list) and \
                self.noise_test_type_cbox.currentText() == 'vs. Azimuth':

            menu = QtWidgets.QMenu()
            set_file_action = menu.addAction('Set file INTO SEAS')
            clear_file_action = menu.addAction('Clear setting')
            action = menu.exec_(event.globalPos())
            item = source.itemAt(event.pos())

            if action == set_file_action or action == clear_file_action:
                set_into_seas = action == set_file_action
                self.set_file_into_seas(item, set_into_seas)

            # if menu.exec_(event.globalPos()):
            #     item = source.itemAt(event.pos())
            #     self.set_file_into_seas(item, event)
                # print(item.text())
                # item.setTextColor("red")
                # item.setText(item.text() + ' (INTO SEAS)')

            return True
        return super(MainWindow, self).eventFilter(source, event)

    def set_file_into_seas(self, item, set_into_seas):
        # manage the file list to allow only one file selected as 'into seas'
        print('now trying to set into seas for file: ', item.text())
        self.get_current_file_list()

        for i in range(self.file_list.count()):  # reset all text in file list
            f = self.file_list.item(i)
            f.setText(f.text().split()[0])  # reset text to filename only

        if set_into_seas:  # set the selected (right-clicked) file as INTO SEAS
            fname_str = item.text()
            item.setText(fname_str + ' ' + self.file_into_seas_str)
            self.update_log('Set file INTO SEAS: ' + fname_str)

            # update the swell direction text box
            try:
                # hdgs = re.search(r"[_]\d{1,3}[T]?[_]\d{1,3}[S]?", fname_str).group().split('_')[1:]
                hdgs = re.search(r"[_]\d{1,3}[T]?(_|.txt)", fname_str).group().split('_')[1:]
                # temp_hdg = float(''.join([c for c in hdgs[0] if c.isdigit()]))
                temp_swell = ''.join([c for c in hdgs[0] if c.isdigit()])
                print('in set_file_into_seas, found hdgs with format _045[T]_000[S], hdgs = ', hdgs)
                self.swell_dir_tb.setText(temp_swell)
                self.update_log('Parsed swell direction ' + self.swell_dir_tb.text() + ' deg from filename')
                self.swell_dir_updated = True

            except:
                self.update_log('Failed to parse swell direction from filename.  Please check the filename formats to '
                                'ensure the true heading is included as, e.g., ''_124T.txt'' for each, then retry '
                                'selecting the file oriented into the swell or enter the swell direction manually')
                self.swell_dir_tb.setText(self.swell_dir_default)
                self.swell_dir_updated = False

        else:
            self.update_log('Cleared INTO SEAS file setting')
            self.swell_dir_tb.setText(self.swell_dir_default)
            self.swell_dir_updated = False

    def show_previous_frequency(self):
        """Show the previous chart"""
        if self.total_charts > 1:
            self.current_chart_index = (self.current_chart_index - 1) % self.total_charts
            self.display_current_frequency()
            self.update_navigation_controls()

    def show_next_frequency(self):
        """Show the next chart"""
        if self.total_charts > 1:
            self.current_chart_index = (self.current_chart_index + 1) % self.total_charts
            self.display_current_frequency()
            self.update_navigation_controls()

    def display_current_frequency(self):
        """Display the current chart"""
        if self.frequency_data and 0 <= self.current_chart_index < len(self.frequency_data):
            try:
                # Get the plot data for the current frequency
                plot_data = self.frequency_data[self.current_chart_index]
                
                # Regenerate the plot using the stored data based on plot type
                plot_type = plot_data.get('plot_type')
                test_type = plot_data.get('test_type')
                
                if plot_type == 'tx_channels':
                    # Handle TX channel plots
                    if plot_data.get('plot_subtype') == 'history':
                        figure = read_bist.plot_tx_z_history(plot_data['bist'],
                                                             save_figs=False,
                                                             output_dir=self.output_dir,
                                                             return_fig=True,
                                                             gui_mode=True)
                    else:
                        figure = self.generate_tx_channel_plot(plot_data['bist'], 
                                                              file_index=plot_data['file_index'],
                                                              plot_style=plot_data['plot_style'],
                                                              save_figs=False,  # GUI display only
                                                              output_dir=self.output_dir)
                elif plot_type == 'rx_channels':
                    # Handle RX channel plots
                    if 'figure_index' in plot_data:
                        # Use the stored figure directly
                        figure = self.all_figures[plot_data['figure_index']]
                    elif 'plot_subtype' in plot_data:
                        bist_plot = plot_data['bist']
                        if 'freq_index' in plot_data:
                            bist_plot = self._create_single_frequency_bist(bist_plot, plot_data['freq_index'])
                        # Handle specific plot subtypes (heatmap vs history)
                        if plot_data['plot_subtype'] == 'heatmap':
                            figure = read_bist.plot_rx_z(bist_plot, save_figs=False, output_dir=self.output_dir, return_fig=True, gui_mode=True)
                        elif plot_data['plot_subtype'] == 'line_heatmap':
                            figure = read_bist.plot_rx_z_line_heatmap(bist_plot, save_figs=False, output_dir=self.output_dir, return_fig=True, gui_mode=True)
                        elif plot_data['plot_subtype'] == 'history':
                            figure = read_bist.plot_rx_z_history(bist_plot, save_figs=False, output_dir=self.output_dir, return_fig=True, gui_mode=True)
                        else:
                            # Fallback to original method
                            figure = self.generate_rx_channel_plot(plot_data['bist'], save_figs=False, output_dir=self.output_dir)
                        if isinstance(figure, list):
                            figure = figure[0] if figure else None
                    elif 'freq_index' in plot_data:
                        # Generate plot for specific frequency
                        figure = self.generate_rx_channel_plot_for_frequency(plot_data['bist'], 
                                                                          plot_data['freq_index'],
                                                                          save_figs=False,
                                                                          output_dir=self.output_dir)
                    else:
                        # Fallback to original method
                        figure = self.generate_rx_channel_plot(plot_data['bist'], 
                                                             save_figs=False,
                                                             output_dir=self.output_dir)
                elif test_type == 'speed_binned_2kt':
                    # Handle 2kt binned plots (check specific test_type first)
                    figure_result = read_bist.plot_rx_noise_binned_2kt(plot_data['bist'], save_figs=False,
                                                               output_dir=self.output_dir,
                                                               test_type='speed',
                                                               param=plot_data['param'],
                                                               param_unit=plot_data['param_unit'],
                                                               param_adjust=plot_data['param_adjust'],
                                                               param_lims=plot_data['param_lims'],
                                                               binned_range_lims=plot_data['binned_range_lims'],
                                                               error_bar_type=plot_data['error_bar_type'],
                                                               individual_type=plot_data['individual_type'],
                                                               calculated_mean=plot_data.get('calculated_mean', 'Arithmetic & Linear Mean'),
                                                               sort=plot_data.get('sort', 'ascending'),
                                                               return_fig=True,
                                                               **self._binned_source_kwargs(plot_data))
                    # Extract figure from tuple (binned functions return (fig, data_dict))
                    if isinstance(figure_result, tuple):
                        figure = figure_result[0]
                    else:
                        figure = figure_result
                elif test_type in ('rpm_binned', 'pitch_binned_deg', 'pitch_binned_pct'):
                    discrete_plot_fn = plot_data.get('plot_function', read_bist.plot_rx_noise_binned_rpm)
                    figure_result = discrete_plot_fn(plot_data['bist'], save_figs=False,
                                                               output_dir=self.output_dir,
                                                               test_type='speed',
                                                               param=plot_data['param'],
                                                               param_unit=plot_data['param_unit'],
                                                               param_adjust=plot_data['param_adjust'],
                                                               param_lims=plot_data['param_lims'],
                                                               binned_range_lims=plot_data['binned_range_lims'],
                                                               error_bar_type=plot_data['error_bar_type'],
                                                               individual_type=plot_data['individual_type'],
                                                               calculated_mean=plot_data.get('calculated_mean', 'Arithmetic & Linear Mean'),
                                                               sort=plot_data.get('sort', 'ascending'),
                                                               return_fig=True,
                                                               **self._binned_source_kwargs(plot_data))
                    # Extract figure from tuple (binned functions return (fig, data_dict))
                    if isinstance(figure_result, tuple):
                        figure = figure_result[0]
                    else:
                        figure = figure_result
                elif plot_type == 'rx_noise_binned' or test_type == 'speed_binned':
                    # Handle 1kt binned plots
                    figure_result = read_bist.plot_rx_noise_binned_new(plot_data['bist'], save_figs=False,
                                                               output_dir=self.output_dir,
                                                               test_type='speed',
                                                               param=plot_data['param'],
                                                               param_unit=plot_data['param_unit'],
                                                               param_adjust=plot_data['param_adjust'],
                                                               param_lims=plot_data['param_lims'],
                                                               binned_range_lims=plot_data['binned_range_lims'],
                                                               error_bar_type=plot_data['error_bar_type'],
                                                               individual_type=plot_data['individual_type'],
                                                               calculated_mean=plot_data.get('calculated_mean', 'Arithmetic & Linear Mean'),
                                                               sort=plot_data.get('sort', 'ascending'),
                                                               return_fig=True,
                                                               **self._binned_source_kwargs(plot_data))
                    # Extract figure from tuple (binned functions return (fig, data_dict))
                    if isinstance(figure_result, tuple):
                        figure = figure_result[0]
                    else:
                        figure = figure_result
                elif plot_type == 'rx_noise' or test_type in ['speed', 'rpm', 'pitch_deg', 'pitch_pct', 'azimuth', 'depth']:
                    # Handle regular RX noise plots
                    figure = read_bist.plot_rx_noise(plot_data['bist'], save_figs=False,
                                                   output_dir=self.output_dir,
                                                   test_type=self._rx_noise_plot_test_type(plot_data['test_type']),
                                                   param=plot_data['param'],
                                                   param_unit=plot_data['param_unit'],
                                                   param_adjust=plot_data['param_adjust'],
                                                   param_lims=plot_data['param_lims'],
                                                   noise_lims=self._rx_noise_range_lims(),
                                                   cmap=plot_data['cmap'],
                                                   sort=plot_data['sort'],
                                                   redblue_center=plot_data.get('redblue_center', 55),
                                                   return_fig=True,
                                                   gui_embed=True)
                else:
                    # Fallback for any other plot types
                    self.update_log(f"Unknown plot type: plot_type={plot_type}, test_type={test_type}")
                    return

                if isinstance(figure, list):
                    freq_index = plot_data.get('freq_index', 0)
                    figure = figure[freq_index] if freq_index < len(figure) else figure[0]
                if figure is None:
                    self.update_log("No figure generated for current chart")
                    return
                
                # Replace the current figure and size it to the plot window
                self._show_figure_on_canvas(
                    figure,
                    plot_type=plot_type,
                    test_type=test_type)
                
                # Force a redraw of the canvas
                self.plot_figure_canvas.draw()
                self.plot_figure_canvas.flush_events()
                QtWidgets.QApplication.processEvents()
                read_bist.attach_rx_noise_speed_hover(figure, self.plot_figure_canvas)
                read_bist.attach_rx_channel_hover(figure, self.plot_figure_canvas)
                read_bist.attach_tx_channel_hover(figure, self.plot_figure_canvas)
                
                self.update_log(f"Displayed chart {self.current_chart_index + 1} of {self.total_charts}")
                
            except Exception as e:
                self.update_log(f"Error displaying frequency plot: {str(e)}")
                import traceback
                self.update_log(f"Traceback: {traceback.format_exc()}")

    def generate_tx_channel_plot(self, bist, file_index=0, plot_style=1, save_figs=True, output_dir=os.getcwd()):
        """Generate a TX channel plot and return the figure object"""
        try:
            # Get the specific file data
            fname_str = bist['filename'][file_index]
            fname_str = fname_str[fname_str.rfind("/") + 1:-4]
            
            # Set min and max Z limits for model
            if bist['tx_limits'][file_index]:
                [zmin, zmax] = bist['tx_limits'][file_index]
            else:
                [zmin, zmax] = read_bist.get_tx_z_limits(bist['model'][file_index])

            # Get number of TX channels and slots for setting up axis ticks
            n_tx_chans = np.size(bist['tx'][file_index], 0)
            n_tx_slots = np.size(bist['tx'][file_index], 1)
            grid_cmap = 'rainbow'  # colormap for grid plot

            # Define font sizes - smaller for GUI display, but larger axis labels for readability
            title_fontsize = 10  # Further reduced from 12 for better GUI fit
            label_fontsize = 7   # Set to 7 as requested
            tick_fontsize = 7    # Set to 7 as requested
            cbar_fontsize = 7    # Further reduced from 8 for better GUI fit
            axfsize = 8          # Further reduced from 10 for better GUI fit

            if plot_style == 1:  # single grid plot oriented vertically
                # Set x ticks and labels on bottom of subplots to match previous MAC figures
                plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = True
                plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = False

                fig, ax = plt.subplots(nrows=1, ncols=1)  # create new figure
                tx_data = bist['tx'][file_index]
                tx_cmap = plt.get_cmap(grid_cmap).copy()
                tx_cmap.set_under('black')
                tx_cmap.set_over('magenta')
                tx_data_min = np.nanmin(tx_data)
                tx_data_max = np.nanmax(tx_data)
                tx_extend = 'neither'
                if tx_data_min < zmin and tx_data_max > zmax:
                    tx_extend = 'both'
                elif tx_data_min < zmin:
                    tx_extend = 'min'
                elif tx_data_max > zmax:
                    tx_extend = 'max'
                im = ax.imshow(tx_data, cmap=tx_cmap, vmin=zmin, vmax=zmax)
                fig._bist_tx_hover = (ax, im, tx_data)
                cbar = fig.colorbar(im, orientation='vertical', extend=tx_extend)
                cbar.set_label(r'Impedance ($\Omega$, f=' + read_bist.tx_frequency_text(bist, file_index=file_index) + ' kHz)', fontsize=cbar_fontsize)

                # Set ticks and labels
                dy_tick = 5
                dx_tick = [2, 4][n_tx_slots >= 12]  # x tick = 2 if <12 slots
                ax.set_yticks(np.arange(0, n_tx_chans + dy_tick - 1, dy_tick))
                x_slot_pos, x_slot_lbl = read_bist._tx_slot_axis_ticks(n_tx_slots, dx_tick)
                ax.set_xticks(x_slot_pos)
                ax.set_yticklabels(np.arange(0, 40, 5), fontsize=tick_fontsize)
                ax.set_xticklabels(x_slot_lbl, fontsize=tick_fontsize)
                ax.set_xlim(-0.5, n_tx_slots - 0.5)

                ax.set_yticks(np.arange(-0.5, (n_tx_chans + 0.5), 1), minor=True)
                ax.set_xticks(np.arange(-0.5, (n_tx_slots + 0.5), 1), minor=True)
                ax.grid(which='minor', color='k', linewidth=2)
                ax.set_xlabel('TX Slot (index starts at 1)', fontsize=label_fontsize)
                ax.set_ylabel('TX Channel (index starts at 0)', fontsize=label_fontsize)

                # Set the super title
                title_str = 'TX Channels BIST\n' + read_bist.tx_channels_id_line(bist, file_index=file_index) + '\n' + \
                            read_bist.tx_channels_detail_line(fname_str, bist, file_index=file_index)
                fig.suptitle(title_str, fontsize=title_fontsize)
                fig.set_size_inches(10, 12)
                read_bist._center_axes_block_in_figure(fig, top_margin=0.88)

            elif plot_style == 2:  # two subplots, line plot on top, grid plot on bottom
                # Set x ticks and labels on top of subplots
                plt.rcParams['xtick.bottom'] = plt.rcParams['xtick.labelbottom'] = False
                plt.rcParams['xtick.top'] = plt.rcParams['xtick.labeltop'] = True
                ztx = np.transpose(bist['tx'][file_index])
                subplot_height_ratio = 1.5
                fig = plt.figure()
                fig.set_size_inches(11, 16)
                fig._bist_tx_style = 2
                gs = gridspec.GridSpec(2, 1, height_ratios=[1, subplot_height_ratio], hspace=0.55)

                # Top plot: line plot for each slot across all channels
                ax1 = plt.subplot(gs[0])
                ztx_channel = np.tile(np.arange(0, n_tx_chans), [n_tx_slots, 1])
                ax1.plot(ztx_channel.transpose(), ztx.transpose())

                ax1.set_xlim(-0.5, n_tx_chans-0.5)
                ax1.set_ylim(zmin, zmax)
                ax1.set(aspect='auto', adjustable='box')

                # Bottom plot: grid plot
                ax2 = plt.subplot(gs[1])
                tx_cmap = plt.get_cmap(grid_cmap).copy()
                tx_cmap.set_under('black')
                tx_cmap.set_over('magenta')
                tx_data_min = np.nanmin(ztx)
                tx_data_max = np.nanmax(ztx)
                tx_extend = 'neither'
                if tx_data_min < zmin and tx_data_max > zmax:
                    tx_extend = 'both'
                elif tx_data_min < zmin:
                    tx_extend = 'min'
                elif tx_data_max > zmax:
                    tx_extend = 'max'
                im = ax2.imshow(ztx, cmap=tx_cmap, vmin=zmin, vmax=zmax)
                ax2.set_aspect('equal', anchor='N')
                plt.gca().invert_yaxis()

                # Set axis ticks for each subplot
                dx_tick = 5
                dy_tick = [2, 4][n_tx_slots >= 12]

                # Set major axes ticks for labels
                x_major_ticks = np.arange(0, n_tx_chans + dx_tick - 1, dx_tick)
                y_major_ticks = np.arange(zmin, zmax + 1, 10)
                ax1.set_xticks(x_major_ticks)
                ax1.set_yticks(y_major_ticks)
                ax2.set_xticks(x_major_ticks)
                y_slot_pos, y_slot_lbl = read_bist._tx_slot_axis_ticks(n_tx_slots, dy_tick)
                ax2.set_yticks(y_slot_pos)

                # minor ticks: line plot matches label spacing; heatmap uses per-cell lines
                ax1.set_xticks(x_major_ticks, minor=True)
                ax1.set_yticks(y_major_ticks, minor=True)
                ax2.set_xticks(np.arange(-0.5, (n_tx_chans+0.5), 1), minor=True)
                ax2.set_yticks(np.arange(-0.5, (n_tx_slots+0.5), 1), minor=True)

                # Set axis tick labels (match major tick positions; do not hardcode 0..40)
                x_tick_labels = [str(int(x)) for x in x_major_ticks]
                ax1.set_xticklabels(x_tick_labels, fontsize=axfsize)
                ax1.set_yticklabels([str(int(y)) for y in y_major_ticks], fontsize=axfsize)
                ax2.set_xticklabels(x_tick_labels, fontsize=axfsize)
                ax2.set_yticklabels(y_slot_lbl, fontsize=axfsize)
                ax2.set_ylim(n_tx_slots - 0.5, -0.5)

                # line plot: grid at label interval; heatmap: per-cell minor grid
                ax1.grid(which='major', color='k', linewidth=1)
                ax2.grid(which='minor', color='k', linewidth=1)

                # Set axis labels
                ax1.set_xlabel('TX Channel (index starts at 0)', fontsize=axfsize)
                ax1.set_ylabel(r'Impedance ($\Omega$, f=' + read_bist.tx_frequency_text(bist, file_index=file_index) + ' kHz)', fontsize=axfsize)
                ax1.xaxis.set_label_position('top')
                ax2.set_ylabel('TX Slot (index starts at 1)', fontsize=axfsize)
                ax2.set_xlabel('TX Channel (index starts at 0)', fontsize=axfsize)
                ax2.xaxis.set_label_position('top')

                # Add colorbar
                cbar = fig.colorbar(im, orientation='horizontal', fraction=0.05, pad=0.05, extend=tx_extend)
                cbar.set_label(r'Impedance ($\Omega$, f=' + read_bist.tx_frequency_text(bist, file_index=file_index) + ' kHz)', fontsize=cbar_fontsize)

                # Set the super title
                title_str = 'TX Channels BIST\n' + read_bist.tx_channels_id_line(bist, file_index=file_index) + '\n' + \
                            read_bist.tx_channels_detail_line(fname_str, bist, file_index=file_index)
                fig.suptitle(title_str, fontsize=title_fontsize)
                fig.subplots_adjust(left=0.10, right=0.96, bottom=0.08, top=0.84, hspace=0.75)

            # Save the figure if requested
            if save_figs:
                fig_name = 'TX_Z_EM' + bist['model'][file_index] + '_SN_' + bist['sn'][file_index] + '_' + fname_str +\
                           '_v' + str(plot_style) + '.png'
                fig.savefig(os.path.join(output_dir, fig_name), dpi=100, bbox_inches='tight')

            return fig

        except Exception as e:
            self.update_log(f"Error generating TX channel plot: {str(e)}")
            return None

    def generate_rx_channel_plot(self, bist, save_figs=True, output_dir=os.getcwd()):
        """Generate an RX channel plot and return the figure object"""
        try:
            # Get the specific file data
            fname_str = bist['filename'][0]
            fname_str = fname_str[fname_str.rfind("/") + 1:-4]
            
            # Define font sizes - smaller for GUI display
            title_fontsize = 10  # Further reduced from 12 for better GUI fit
            label_fontsize = 7   # Further reduced from 8 for better GUI fit
            tick_fontsize = 6    # Further reduced from 7 for better GUI fit
            cbar_fontsize = 7    # Further reduced from 8 for better GUI fit
            
            # Generate the RX channel plot using the existing function but with return_fig=True
            figure = read_bist.plot_rx_z(bist, save_figs=save_figs, output_dir=self.output_dir, return_fig=True)
            
            if figure:
                # Apply smaller font sizes for GUI display
                # Update title font size
                if figure.get_suptitle():
                    # get_suptitle() returns a string, not a text object
                    current_title = figure.get_suptitle()
                    figure.suptitle(current_title, fontsize=title_fontsize)
                
                # Update axis labels and tick labels
                for ax in figure.get_axes():
                    # Update axis labels
                    if ax.get_xlabel():
                        ax.set_xlabel(ax.get_xlabel(), fontsize=label_fontsize)
                    if ax.get_ylabel():
                        ax.set_ylabel(ax.get_ylabel(), fontsize=label_fontsize)
                    
                    # Update tick labels
                    ax.tick_params(axis='both', which='major', labelsize=tick_fontsize)
                    ax.tick_params(axis='both', which='minor', labelsize=tick_fontsize)
                
                # Update colorbar if it exists
                for ax in figure.get_axes():
                    if hasattr(ax, 'collections') and ax.collections:
                        for collection in ax.collections:
                            if hasattr(collection, 'colorbar') and collection.colorbar:
                                # Get the current colorbar label text safely
                                try:
                                    current_label = collection.colorbar.get_label_text()
                                    collection.colorbar.set_label(current_label, fontsize=cbar_fontsize)
                                except AttributeError:
                                    # If get_label_text() doesn't exist, try alternative methods
                                    try:
                                        current_label = collection.colorbar.get_label()
                                        collection.colorbar.set_label(current_label, fontsize=cbar_fontsize)
                                    except:
                                        # Skip if we can't get the label
                                        pass
            
            return figure

        except Exception as e:
            self.update_log(f"Error generating RX channel plot: {str(e)}")
            return None

    def generate_rx_channel_plot_for_frequency(self, bist, freq_index, save_figs=True, output_dir=os.getcwd()):
        """Generate an RX channel plot for a specific frequency and return the figure object"""
        try:
            # Get the specific file data
            fname_str = bist['filename'][0]
            fname_str = fname_str[fname_str.rfind("/") + 1:-4]
            
            # Define font sizes - smaller for GUI display
            title_fontsize = 10  # Further reduced from 12 for better GUI fit
            label_fontsize = 7   # Further reduced from 8 for better GUI fit
            tick_fontsize = 6    # Further reduced from 7 for better GUI fit
            cbar_fontsize = 7    # Further reduced from 8 for better GUI fit
            
            # Create a modified BIST data structure with only the specific frequency
            # This is a bit of a hack, but it's the cleanest way to get a single frequency plot
            bist_single_freq = self._create_single_frequency_bist(bist, freq_index)
            
            # Generate the RX channel plot using the existing function but with return_fig=True
            figure = read_bist.plot_rx_z(bist_single_freq, save_figs=save_figs, output_dir=output_dir, return_fig=True)
            
            if figure:
                # Apply smaller font sizes for GUI display
                # Update title font size
                if figure.get_suptitle():
                    # get_suptitle() returns a string, not a text object
                    current_title = figure.get_suptitle()
                    figure.suptitle(current_title, fontsize=title_fontsize)
                
                # Update axis labels and tick labels
                for ax in figure.get_axes():
                    # Update axis labels
                    if ax.get_xlabel():
                        ax.set_xlabel(ax.get_xlabel(), fontsize=label_fontsize)
                    if ax.get_ylabel():
                        ax.set_ylabel(ax.get_ylabel(), fontsize=label_fontsize)
                    
                    # Update tick labels
                    ax.tick_params(axis='both', which='major', labelsize=tick_fontsize)
                    ax.tick_params(axis='both', which='minor', labelsize=tick_fontsize)
                
                # Update colorbar if it exists
                for ax in figure.get_axes():
                    if hasattr(ax, 'collections') and ax.collections:
                        for collection in ax.collections:
                            if hasattr(collection, 'colorbar') and collection.colorbar:
                                # Get the current colorbar label text safely
                                try:
                                    current_label = collection.colorbar.get_label_text()
                                    collection.colorbar.set_label(current_label, fontsize=cbar_fontsize)
                                except AttributeError:
                                    # If get_label_text() doesn't exist, try alternative methods
                                    try:
                                        current_label = collection.colorbar.get_label()
                                        collection.colorbar.set_label(current_label, fontsize=cbar_fontsize)
                                    except:
                                        # Skip if we can't get the label
                                        pass
                

            
            return figure

        except Exception as e:
            self.update_log(f"Error generating RX channel plot for frequency {freq_index}: {str(e)}")
            import traceback
            self.update_log(f"Traceback: {traceback.format_exc()}")
            return None

    def _normalize_plot_figures(self, figure_or_list):
        """Return a list of matplotlib figures from a plot function return value."""
        if figure_or_list is None:
            return []
        if isinstance(figure_or_list, list):
            return [fig for fig in figure_or_list if fig is not None]
        return [figure_or_list]

    def _rx_channel_chart_labels(self, bist, plot_subtype):
        """Navigation names in the same order plot_rx_z / history emit figures."""
        if plot_subtype == 'history':
            freqs = []
            for freq_map in bist.get('freq_range', []):
                if isinstance(freq_map, dict):
                    for values in freq_map.values():
                        if isinstance(values, (list, tuple)):
                            freqs.extend(values)
            labels = []
            for freq in sorted(set(freqs), key=str):
                labels.append('RX Channels History - ' + str(freq).replace('.0', '') + ' kHz')
            return labels

        prefix = {
            'heatmap': 'RX Channels Heatmap',
            'line_heatmap': 'RX Channels Line+Heatmap',
        }.get(plot_subtype, 'RX Channels')
        labels = []
        filenames = bist.get('filename', [])
        rx = bist.get('rx', [])
        freq_range = bist.get('freq_range', [])
        for i in range(len(filenames)):
            fname = str(filenames[i]).replace('\\', '/')
            fname = fname[fname.rfind('/') + 1:]
            if fname.lower().endswith('.txt'):
                fname = fname[:-4]
            tests = rx[i] if i < len(rx) and isinstance(rx[i], dict) else {}
            freq_map = freq_range[i] if i < len(freq_range) and isinstance(freq_range[i], dict) else {}
            multi_test = len(tests) > 1
            for t in tests.keys():
                freqs = freq_map.get(t, [])
                if not isinstance(freqs, (list, tuple)):
                    freqs = [freqs]
                test_bit = (' test ' + str(t)) if multi_test else ''
                for freq in freqs:
                    labels.append(prefix + ' - ' + fname + test_bit + ' - ' + str(freq).replace('.0', '') + ' kHz')
        return labels

    def _append_rx_channel_plots_by_test(self, heatmap_figures, line_figures, bist, fname_str, freq_list):
        """Register heatmap then line+heatmap for each test before the next test."""
        heatmaps = self._normalize_plot_figures(heatmap_figures)
        lines = self._normalize_plot_figures(line_figures)
        heat_labels = self._rx_channel_chart_labels(bist, 'heatmap')
        line_labels = self._rx_channel_chart_labels(bist, 'line_heatmap')
        for i in range(max(len(heatmaps), len(lines))):
            if i < len(heatmaps):
                label = heat_labels[i] if i < len(heat_labels) else None
                self._append_rx_channel_plot_results(
                    heatmaps[i], bist, 'heatmap', fname_str, freq_list, label=label)
            if i < len(lines):
                label = line_labels[i] if i < len(line_labels) else None
                self._append_rx_channel_plot_results(
                    lines[i], bist, 'line_heatmap', fname_str, freq_list, label=label)

    def _append_rx_channel_plot_results(self, figure_or_list, bist, plot_subtype, fname_str, freq_list, label=None):
        """Register one or more RX channel figures for GUI navigation."""
        labels = [label] if label is not None else self._rx_channel_chart_labels(bist, plot_subtype)
        subtype_labels = {
            'heatmap': 'RX Channels Heatmap',
            'line_heatmap': 'RX Channels Line+Heatmap',
            'history': 'RX Channels History',
        }
        label_prefix = subtype_labels.get(plot_subtype, 'RX Channels')
        for chart_index, fig in enumerate(self._normalize_plot_figures(figure_or_list)):
            fig = self.apply_gui_font_sizes(fig)
            figure_index = len(self.all_figures)
            self.frequency_data.append({
                'bist': bist,
                'plot_type': 'rx_channels',
                'plot_subtype': plot_subtype,
                'freq_index': chart_index,
                'figure_index': figure_index,
            })
            self.all_figures.append(fig)
            self.total_charts += 1
            if chart_index < len(labels):
                self.freq_list.append(labels[chart_index])
            else:
                freq_str = str(freq_list[chart_index]) if chart_index < len(freq_list) else "Unknown"
                self.freq_list.append(f"{label_prefix} - {fname_str} - {freq_str} kHz")

    def apply_gui_font_sizes(self, figure):
        """Apply smaller font sizes to a figure for GUI display"""
        try:
            # Define font sizes - smaller for GUI display
            title_fontsize = 8   # Further reduced from 10 for better GUI fit
            label_fontsize = 6   # Further reduced from 7 for better GUI fit
            tick_fontsize = 5    # Further reduced from 6 for better GUI fit
            cbar_fontsize = 6    # Further reduced from 7 for better GUI fit
            
            if figure:
                # Apply smaller font sizes for GUI display
                # Update title font size
                if figure.get_suptitle():
                    # get_suptitle() returns a string, not a text object
                    current_title = figure.get_suptitle()
                    figure.suptitle(current_title, fontsize=title_fontsize)
                
                # Update axis labels and tick labels
                for ax in figure.get_axes():
                    # Update axis labels
                    if ax.get_xlabel():
                        current_xlabel = ax.get_xlabel()
                        ax.set_xlabel(current_xlabel, fontsize=label_fontsize)
                    if ax.get_ylabel():
                        current_ylabel = ax.get_ylabel()
                        ax.set_ylabel(current_ylabel, fontsize=label_fontsize)
                    
                    # Update tick labels
                    ax.tick_params(axis='both', which='major', labelsize=tick_fontsize)
                    ax.tick_params(axis='both', which='minor', labelsize=tick_fontsize)
                
                # Update colorbar if it exists
                for ax in figure.get_axes():
                    if hasattr(ax, 'collections') and ax.collections:
                        for collection in ax.collections:
                            if hasattr(collection, 'colorbar') and collection.colorbar:
                                # Get the current colorbar label text safely
                                try:
                                    current_label = collection.colorbar.get_label_text()
                                    collection.colorbar.set_label(current_label, fontsize=cbar_fontsize)
                                except AttributeError:
                                    # If get_label_text() doesn't exist, try alternative methods
                                    try:
                                        current_label = collection.colorbar.get_label()
                                        collection.colorbar.set_label(current_label, fontsize=cbar_fontsize)
                                    except:
                                        # Skip if we can't get the label
                                        pass
            
            return figure
            
        except Exception as e:
            self.update_log(f"Error applying GUI font sizes: {str(e)}")
            return figure

    @staticmethod
    def _slice_test_freq_data(data, freq_index):
        """Extract one frequency from list- or dict-keyed per-test BIST fields."""
        if isinstance(data, list):
            if freq_index < len(data):
                return [data[freq_index]]
            return []
        if isinstance(data, dict):
            if freq_index in data:
                return [data[freq_index]]
            return []
        return data

    def _create_single_frequency_bist(self, bist, freq_index):
        """Create a modified BIST data structure with only the specified frequency"""
        try:
            freq_keys = [
                'rx', 'rx_array', 'freq_range', 'test_datetime',
                'rx_limits', 'rx_array_limits', 'rx_units',
            ]
            bist_single_freq = {}
            for key in bist:
                if key in freq_keys:
                    if isinstance(bist[key], list):
                        bist_single_freq[key] = []
                        for file_idx in range(len(bist[key])):
                            if isinstance(bist[key][file_idx], dict):
                                bist_single_freq[key].append({})
                                for test_idx in bist[key][file_idx]:
                                    test_data = bist[key][file_idx][test_idx]
                                    if key == 'test_datetime':
                                        bist_single_freq[key][file_idx][test_idx] = test_data
                                    else:
                                        bist_single_freq[key][file_idx][test_idx] = self._slice_test_freq_data(
                                            test_data, freq_index)
                            else:
                                bist_single_freq[key].append(bist[key][file_idx])
                    else:
                        bist_single_freq[key] = bist[key]
                else:
                    bist_single_freq[key] = bist[key]

            return bist_single_freq
            
        except Exception as e:
            self.update_log(f"Error creating single frequency BIST data: {str(e)}")
            import traceback
            self.update_log(f"Traceback: {traceback.format_exc()}")
            return bist  # Return original if modification fails

    def _clear_shown_plots(self):
        """Drop every chart and return the plot window to the startup credit page."""
        shown = getattr(self, 'plot_figure', None)
        for figure in list(getattr(self, 'all_figures', []) or []):
            if figure is shown:
                continue
            try:
                plt.close(figure)
            except Exception:
                pass
        self.all_figures = []
        self.frequency_data = []
        self.freq_list = []
        self.current_chart_index = 0
        self.total_charts = 0
        self.last_plotted_bist = None
        self.last_bist_test_type = None
        self.last_plotted_files = []
        self.last_into_seas_file = None
        if shown is not None:
            shown.clear()
            try:
                self.plot_figure_canvas.draw_idle()
            except Exception:
                pass
        self._show_about_in_plot_window()
        self.update_navigation_controls()

    def update_navigation_controls(self):
        """Update the navigation controls based on current state"""
        if self.total_charts > 1:
            # Enable navigation buttons
            self.prev_chart_btn.setEnabled(True)
            self.next_chart_btn.setEnabled(True)
            
            # Update chart label
            if self.freq_list and self.current_chart_index < len(self.freq_list):
                freq_name = self.freq_list[self.current_chart_index]
                self.freq_label.setText(f"Chart: {freq_name} ({self.current_chart_index + 1} of {self.total_charts})")
            else:
                self.freq_label.setText(f"Chart: {self.current_chart_index + 1} of {self.total_charts}")
        elif self.total_charts == 1:
            # Disable navigation buttons for single chart
            self.prev_chart_btn.setEnabled(False)
            self.next_chart_btn.setEnabled(False)
            self.freq_label.setText("Chart: Single")
        else:
            self.prev_chart_btn.setEnabled(False)
            self.next_chart_btn.setEnabled(False)
            self.freq_label.setText("Chart: None")


class NewPopup(QtWidgets.QWidget):  # new class for additional plots
    def __init__(self):
        QtWidgets.QWidget.__init__(self)


def load_bist_session_config():
    """Load session configuration from file."""
    import json
    import os
    
    config_file = os.path.join(os.path.expanduser('~'), '.bist_session.json')
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    else:
        return {}

def save_bist_session_config(config):
    """Save session configuration to file."""
    import json
    import os
    
    config_file = os.path.join(os.path.expanduser('~'), '.bist_session.json')
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving session config: {e}")

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    apply_dark_theme(app)
    app.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), "media", "mac.ico")))

    main = MainWindow()
    main.show()

    sys.exit(app.exec())
