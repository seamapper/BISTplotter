# BISTplotter

![Example Plot](media/BIST_Plotter.jpg)

A graphical tool for analyzing and visualizing Kongsberg multibeam echosounder Built-In Self-Test (BIST) files. BISTplotter helps assess EM multibeam system performance and hardware health by parsing and plotting various BIST test results.

## Features

BISTplotter supports multiple BIST test types:

- **TX Channels Impedance** - Plot impedance of TX channels at the transducer, measured through the TRU
- **RX Channels Impedance** - Plot impedance of RX channels measured at the receiver and at the transducer
- **RX Noise Level** - Plot noise levels perceived by the RX system across all channels
- **RX Noise Spectrum** - Visualize RX spectrum BIST data collected at different speeds and headings

The application provides an intuitive GUI for:
- Loading and managing multiple BIST files
- Interactive plotting with navigation controls
- System information tracking (model, serial number, date)
- Customizable test parameters
- Export capabilities for analysis results
- **Dark theme** – GUI uses a dark theme regardless of system settings (plot area keeps default white background)
- **RX Noise vs Speed** – Values outside the 30–70 dB colorbar range are shown in black (below 30 dB) or magenta (above 70 dB), with console warnings when data exceeds the range
- **Colormaps** – Jet, Inferno, Hot, RedBlue, and CoolWarm. Inferno and Hot use custom ranges (bottom at step 40 and 24 respectively). RedBlue (bwr) and CoolWarm support a configurable **Center** (inflection point in dB, default 55) for the blue–white–red transition
- **TX/RX channel out-of-range coloring** – TX and RX channel heatmaps indicate values outside the colorbar range using black (below min) and magenta (above max), including colorbar extend indicators
- **Heatmap hover tooltips** – GUI tooltips (upper-left corner) show per-cell values:
  - TX Channels style-1 heatmap: TX Slot, TX Channel, Impedance
  - RX Channels heatmap: RX Channel, RX Board, Impedance
- **Out-of-spec text reports** – When you plot TX or RX Channels BIST, report files are written to the output directory:
  - `TX_OOS_EM<model>_SN_<sn>_from_text_file_<filename>.txt` — TX channel, TX slot, impedance (ohms)
  - `RX_ARRAY_OOS_EM<model>_SN_<sn>_from_text_file_<filename>.txt` — test, frequency, RX board, RX channel, impedance, and spec limits
- **TX Channels GUI** – Navigate all three TX views in the plot window (style 1 heatmap, style 2 line+grid, and TX history). TX history uses GUI-friendly title/legend sizing and layout; exported history plots are unchanged
- **SIS 5 TX slot parsing** – Combined TX BIST files with multiple impedance tables (e.g. slots 1–10 and 11–14) are concatenated correctly; slot axis labels use a fixed interval and match the real slot count (no phantom extra columns)
- **TX plot layout** – Style-1 TX heatmaps are centered under the plot title in the GUI (colorbar included in layout)

## Download

Pre-built executables are available in the [Releases](https://github.com/seamapper/BISTplotter/releases) section. Download the latest release for your operating system.

## Requirements

### For Running the Executable
- Windows, macOS, or Linux (depending on the release)
- No additional dependencies required

### For Running from Source
- Python 3.8 or higher
- PyQt6
- NumPy
- Matplotlib

## Installation

### Using the Executable (Recommended)

1. Go to the [Releases](https://github.com/seamapper/BISTplotter/releases) page
2. Download the appropriate executable for your operating system
3. Extract and run the executable

### Running from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/seamapper/BISTplotter.git
   cd BISTplotter
   ```

2. Install dependencies:
   ```bash
   pip install PyQt6 numpy matplotlib
   ```

3. Run the application:
   ```bash
   python bist_plotter.py
   ```

## Usage

1. **Select BIST Test Type**: Choose the type of BIST test you want to analyze from the dropdown menu
2. **Load Files**: Click "Add Files" to select one or more BIST text files
3. **Enter System Information**: Provide the multibeam model, serial number, and test date
4. **Configure Parameters**: Adjust any custom parameters as needed
5. **Plot**: Click "Plot BIST" to generate visualizations
6. **Navigate**: Use the navigation controls to browse through multiple plots

### Input File Formats

- **TX Channels Impedance**: Text file saved from a telnet session running all TX Channels BISTs (these results are not saved to text file when running BISTs in the SIS interface)
- **RX Channels Impedance**: Standard BIST text file saved from the Kongsberg SIS interface
- **RX Noise/Spectrum**: BIST text file, ideally with multiple (10-20) BISTs saved to one text file for better statistical analysis

### Tips

- For RX Noise analysis, collect 10-20 BISTs per condition (e.g., per speed) to reduce the impact of transient noises
- Save one text file per condition (e.g., one file per vessel speed) for organized analysis
- Factory limits for acceptable BIST levels are automatically parsed from the text file when available
- For **SIS 5 TX Channels** combined files, impedance may appear in multiple blocks (separate slot-index header rows per group of slots); the plotter merges them into one heatmap
- Out-of-spec reports are generated automatically when plotting; check the output directory and the Activity Log for filenames

### Output reports (TX / RX Channels)

| Report | When generated | Contents |
|--------|----------------|----------|
| `TX_OOS_*.txt` | TX Channels plot | TX Channel (0-based), TX Slot (1-based), impedance |
| `RX_ARRAY_OOS_*.txt` | RX Channels plot | Out-of-spec RX array elements with test, frequency, board, channel, and limits |

If no elements are out of spec, the report still states that explicitly.

## Supported Systems

BISTplotter was developed and tested primarily with:
- **EM302** (SIS 4 format)
- **EM710** (SIS 4 format)
- **EM122** (SIS 4 format)
- **EM2040** (with some limitations for RX Noise BIST files)

Support for other formats and features may require additional development. SIS 5 model parsing was updated in v2026.3 to correctly extract model numbers (e.g. EM2040, EM304) from the BIST header. **EM304** and other SIS 5 systems with split TX impedance tables are supported.

## Known Limitations

- `N_RX_boards` is typically 4, but in some cases will be 2; this is currently set manually and will eventually be detected automatically
- EM2040 RX Noise BIST files may include columns corresponding to frequency, not RX board; additional development is needed to handle this smoothly, especially between SIS 4 and SIS 5 formats
- RX impedance limits are not automatically detected; these can be found in the BIST text file and manually adjusted if needed
- All impedance tests are meant as proxies for hardware health and not as replacement for direct measurement with Kongsberg tools

## Version

Current version: **2026.7** (see `version.py`)

## Authors

- **kjerram** - Initial work and vision
- **pjohnson** - Further development 

## License

This project is licensed under the BSD 3-Clause License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025, Center for Coastal and Ocean Mapping, University of New Hampshire

## Acknowledgments

Developed at the Center for Coastal and Ocean Mapping (CCOM) at the University of New Hampshire, in collaboration with the Joint Hydrographic Center (JHC) and the Marine Acoustics Center (MAC).

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Issues

If you encounter any problems or have feature requests, please open an issue on the [GitHub Issues](https://github.com/seamapper/BISTplotter/issues) page.


