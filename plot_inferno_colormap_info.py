"""
Plot the original matplotlib Inferno colormap: RGBA values and color patches.
Run: python plot_inferno_colormap_info.py
Output: inferno_colormap_info.png
"""
import numpy as np
import matplotlib
matplotlib.use('Agg')  # no display window
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def main():
    inferno = plt.get_cmap('inferno')
    t = np.linspace(0, 1, 256)
    colors = inferno(t)

    # Sample every 4 steps across full range (0, 4, 8, ..., 252, 255) so no big jump
    indices = list(range(0, 256, 4))
    if indices[-1] != 255:
        indices.append(255)
    n_rows = len(indices)

    fig, ax = plt.subplots(figsize=(11, 4 + n_rows * 0.14))
    ax.set_axis_off()

    # ---- Full colormap strip at top ----
    strip_height = 0.5
    top = n_rows * 0.14 + 2.5
    ax.imshow(colors[np.newaxis, :, :3], aspect='auto',
              extent=[0, 10, top - strip_height, top], interpolation='nearest')
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, top + 0.5)
    ax.text(5, top + 0.25, 'Original Inferno (index 0–255)', ha='center', fontsize=11, fontweight='bold')

    # ---- Table header ----
    y0 = top - 0.7
    ax.text(0.2, y0, 'Index', fontsize=9, fontweight='bold')
    ax.text(0.9, y0, 'Color', fontsize=9, fontweight='bold')
    ax.text(1.8, y0, 'R', fontsize=9, fontweight='bold')
    ax.text(2.4, y0, 'G', fontsize=9, fontweight='bold')
    ax.text(3.0, y0, 'B', fontsize=9, fontweight='bold')
    ax.text(3.6, y0, 'A', fontsize=9, fontweight='bold')
    ax.text(4.2, y0, 'Hex', fontsize=9, fontweight='bold')

    row_height = 0.14
    for row, i in enumerate(indices):
        y = y0 - (row + 1) * row_height
        r, g, b, a = colors[i]
        hex_str = '#{:02X}{:02X}{:02X}'.format(int(r*255), int(g*255), int(b*255))

        ax.text(0.2, y, str(i), fontsize=7, va='center')
        rect = mpatches.Rectangle((0.75, y - 0.055), 0.35, 0.11, facecolor=colors[i], edgecolor='gray', linewidth=0.3)
        ax.add_patch(rect)
        ax.text(1.8, y, f'{r:.4f}', fontsize=6, va='center')
        ax.text(2.4, y, f'{g:.4f}', fontsize=6, va='center')
        ax.text(3.0, y, f'{b:.4f}', fontsize=6, va='center')
        ax.text(3.6, y, f'{a:.4f}', fontsize=6, va='center')
        ax.text(4.2, y, hex_str, fontsize=6, va='center', family='monospace')

    ax.text(5, -0.2, 'Every 4th index (0, 4, 8, …, 252, 255) – full progression', ha='center', fontsize=9)
    ax.set_title('Matplotlib Inferno colormap – sample entries with color', fontsize=12, pad=12)
    plt.tight_layout()
    out_path = 'inferno_colormap_info.png'
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    print('Saved', out_path)
    plt.close()

if __name__ == '__main__':
    main()
