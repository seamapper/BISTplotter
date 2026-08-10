import read_bist
import numpy as np

fname = r'C:/Users/pjohnson/Downloads/20260806-094757-EM712_71-combined_Vsl drifting 784mWD EK80 OFF ADCP OFF.txt'
_, sis = read_bist.verify_bist_type(fname)
bist = read_bist.parse_rx_z(fname, sis_version=sis)

# Simulate appendDict - single file
z = read_bist.init_bist_dict(2)
read_bist.appendDict(z, bist)
# Add required fields that appendDict might miss
for k in ['filename', 'model', 'sn', 'sis_version']:
    if not z[k]:
        z[k] = [getattr(bist, k, None) or bist.get(k, '712')]

# Fix z structure like GUI does
if 'filename' not in bist:
    bist['filename'] = [fname]
z['filename'] = [fname]
z['model'] = ['712']
z['sn'] = [bist.get('sn', 'PU-10038')]
z['sis_version'] = [sis]

print('=== Full plot limits ===')
for f in range(2):
    lim = z['rx_limits'][0][0][f]
    data = z['rx'][0][0][f]
    paired = read_bist._pair_limits(lim)
    print('f=%d limits=%s paired=%s data min/max=%.3f/%.3f in_range=%s' % (
        f, lim, paired, np.nanmin(data), np.nanmax(data),
        paired[0] <= np.nanmin(data) and np.nanmax(data) <= paired[1]))

def create_single_frequency_bist(bist, freq_index):
    """Copy of bist_plotter._create_single_frequency_bist"""
    bist_single_freq = {}
    for key in bist:
        if key in ['rx', 'rx_array', 'freq_range', 'test_datetime', 'rx_limits', 'rx_array_limits', 'rx_units']:
            if isinstance(bist[key], list):
                bist_single_freq[key] = []
                for file_idx in range(len(bist[key])):
                    if isinstance(bist[key][file_idx], dict):
                        bist_single_freq[key].append({})
                        for test_idx in bist[key][file_idx]:
                            if isinstance(bist[key][file_idx][test_idx], list):
                                if freq_index < len(bist[key][file_idx][test_idx]):
                                    bist_single_freq[key][file_idx][test_idx] = [bist[key][file_idx][test_idx][freq_index]]
                                else:
                                    bist_single_freq[key][file_idx][test_idx] = []
                            else:
                                bist_single_freq[key][file_idx][test_idx] = bist[key][file_idx][test_idx]
                    else:
                        bist_single_freq[key].append(bist[key][file_idx])
            else:
                bist_single_freq[key] = bist[key]
        else:
            bist_single_freq[key] = bist[key]
    return bist_single_freq

print('\n=== After single-freq slice (85 kHz, index=1) ===')
z85 = create_single_frequency_bist(z, 1)
print('rx_limits structure:', z85['rx_limits'])
for f in range(len(z85['rx_limits'][0][0])):
    lim = z85['rx_limits'][0][0][f]
    data = z85['rx'][0][0][f]
    try:
        paired = read_bist._pair_limits(lim)
        print('f=%d limits=%s paired=%s data min/max=%.3f/%.3f' % (
            f, lim, paired, np.nanmin(data), np.nanmax(data)))
    except Exception as e:
        print('f=%d ERROR: %s limits=%s' % (f, e, lim))

print('\n=== rx_units after slice ===')
print('full:', z['rx_units'])
print('85kHz slice:', z85['rx_units'])
