import read_bist
import numpy as np

fname = r'C:/Users/pjohnson/Downloads/20260806-094757-EM712_71-combined_Vsl drifting 784mWD EK80 OFF ADCP OFF.txt'
_, sis = read_bist.verify_bist_type(fname)
bist = read_bist.parse_rx_z(fname, sis_version=sis)
print('rx_limits', bist['rx_limits'])
print('freq_range', bist['freq_range'])
for t in bist['rx'][0]:
    for f in range(len(bist['freq_range'][0][t])):
        lim = bist['rx_limits'][0][t][f]
        data = bist['rx'][0][t][f]
        freq = bist['freq_range'][0][t][f]
        print('f=%d freq=%s limits=%s data min/max=%.3f/%.3f' % (f, freq, lim, np.nanmin(data), np.nanmax(data)))
