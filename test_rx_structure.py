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

for key in ['rx', 'rx_array', 'freq_range', 'rx_limits', 'rx_units']:
    val = z[key][0][0]
    print('%s type=%s val=%s' % (key, type(val).__name__, val if key != 'rx' else {k: np.shape(v) for k,v in val.items()}))
