# BISTplotter

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

## Supported Systems

BISTplotter was developed and tested primarily with:
- **EM302** (SIS 4 format)
- **EM710** (SIS 4 format)
- **EM122** (SIS 4 format)
- **EM2040** (with some limitations for RX Noise BIST files)

Support for other formats and features may require additional development.

## Known Limitations

- `N_RX_boards` is typically 4, but in some cases will be 2; this is currently set manually and will eventually be detected automatically
- EM2040 RX Noise BIST files may include columns corresponding to frequency, not RX board; additional development is needed to handle this smoothly, especially between SIS 4 and SIS 5 formats
- RX impedance limits are not automatically detected; these can be found in the BIST text file and manually adjusted if needed
- All impedance tests are meant as proxies for hardware health and not as replacement for direct measurement with Kongsberg tools

## Version

Current version: **2025.2**

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


