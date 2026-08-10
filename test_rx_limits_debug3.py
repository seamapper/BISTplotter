import read_bist
import numpy as np

fname = r'C:/Users/pjohnson/Downloads/20260806-094757-EM712_71-combined_Vsl drifting 784mWD EK80 OFF ADCP OFF.txt'
_, sis = read_bist.verify_bist_type(fname)
parsed = read_bist.parse_rx_z(fname, sis_version=sis)

z = read_bist.init_bist_dict(2)
read_bist.appendDict(z, parsed)
z['filename'] = [fname]
z['model'] = ['712']
z['sn'] = [parsed.get('sn', 'PU-10038')]
z['sis_version'] = [sis]

print('Structure check:')
print('  z[rx][0] keys:', z['rx'][0].keys())
print('  len freqs:', len(z['rx'][0][0]))
print('  f=0 min/max:', np.nanmin(z['rx'][0][0][0]), np.nanmax(z['rx'][0][0][0]))
print('  f=1 min/max:', np.nanmin(z['rx'][0][0][1]), np.nanmax(z['rx'][0][0][1]))
print('  rx_limits[0][0]:', z['rx_limits'][0][0])

def slice_test_freq_data(data, freq_index):
    if isinstance(data, list):
        if freq_index < len(data):
            return [data[freq_index]]
        return []
    if isinstance(data, dict):
        if freq_index in data:
            return [data[freq_index]]
        return []
    return data

def create_single_frequency_bist(bist, freq_index):
    freq_keys = ['rx', 'rx_array', 'freq_range', 'test_datetime', 'rx_limits', 'rx_array_limits', 'rx_units']
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
                                bist_single_freq[key][file_idx][test_idx] = slice_test_freq_data(test_data, freq_index)
                    else:
                        bist_single_freq[key].append(bist[key][file_idx])
            else:
                bist_single_freq[key] = bist[key]
        else:
            bist_single_freq[key] = bist[key]
    return bist_single_freq

for fi in [0, 1]:
    zf = create_single_frequency_bist(z, fi)
    data = zf['rx'][0][0][0]
    lim = zf['rx_limits'][0][0][0]
    paired = read_bist._pair_limits(lim)
    print('\nAfter slice freq_index=%d:' % fi)
    print('  freq_range:', zf['freq_range'][0][0])
    print('  limits:', lim, '->', paired)
    print('  data min/max:', np.nanmin(data), np.nanmax(data))
    print('  in_range:', paired[0] <= np.nanmin(data) and np.nanmax(data) <= paired[1])

# Also test initial plot (no regeneration)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

figs = read_bist.plot_rx_z(z, save_figs=False, return_fig=True, gui_mode=True)
if not isinstance(figs, list):
    figs = [figs]
print('\n=== Initial plot_rx_z figures ===')
for idx, fig in enumerate(figs):
    for ax in fig.axes:
        for im in ax.images:
            arr = im.get_array()
            clim = im.get_clim()
            print('  fig[%d] clim=%s data min/max=%.3f/%.3f extend=%s' % (
                idx, clim, np.nanmin(arr), np.nanmax(arr), im.get_cmap().name))

# Regenerated plot for 85 kHz
z85 = create_single_frequency_bist(z, 1)
fig85 = read_bist.plot_rx_z(z85, save_figs=False, return_fig=True, gui_mode=True)
if isinstance(fig85, list):
    fig85 = fig85[0]
print('\n=== Regenerated 85 kHz plot ===')
for ax in fig85.axes:
    for im in ax.images:
        arr = im.get_array()
        clim = im.get_clim()
        print('  clim=%s data min/max=%.3f/%.3f' % (clim, np.nanmin(arr), np.nanmax(arr)))
plt.close('all')
