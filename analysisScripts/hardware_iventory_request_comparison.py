from datetime import datetime, date

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATA_PATH_CHECKED_OUT = 'cleanedData/hardware_items.csv'
DATA_PATH_INIT = "cleanedData/hardware_initial_inventory.csv"

hardwareRequests = pd.read_csv(DATA_PATH_CHECKED_OUT)
hardwareInventory = pd.read_csv(DATA_PATH_INIT)

hardwareRequests['requested_at_pt'] = pd.to_datetime(hardwareRequests['requested_at_pt'], format="%Y-%m-%d %H:%M:%S")
hardwareInventory['requested_at_pt'] = pd.to_datetime(hardwareRequests['requested_at_pt'], format="%Y-%m-%d %H:%M:%S")

# print(hardwareInventory.columns)

hardwareTypeRequests = hardwareRequests[['item_category']]
hardwareTypeInventory = hardwareInventory[['category', 'initial_quantity']]

binMinutes = 60
binFreq = pd.Timedelta(minutes=binMinutes)


# Categorize and group. observed=False keeps empty bins as NaN so the line breaks
# over gaps (e.g. overnight) instead of drawing a false connection across them.
# hardwareRequests['time_bins'] = pd.cut(hardwareRequests['requested_at_pt'], bins=bins, right=False)
# Named aggregation gives the count its own column name, so the category only lives in the index
groupedRequests = hardwareTypeRequests.groupby('item_category', observed=False).agg(request_lines=('item_category', 'count'))
groupedInventory = hardwareTypeInventory.groupby('category', observed=False).agg(initial_quantity=('initial_quantity', 'sum'))

# Both frames are indexed by category, so merge on the indexes rather than by column name
groupedTable = pd.merge(groupedRequests, groupedInventory, left_index=True, right_index=True, how='left')
groupedTable.index.name = 'category'
groupedTable['proportion of requests/inventory'] = (groupedTable['request_lines'] / groupedTable['initial_quantity']) * 100
print(groupedTable.head())

# ---- Plot --------------------------------------------------------------------
plotTitle = 'Hardware requests as a share of initial inventory, Cal Hacks 13.0'
outputPath = 'visualizations/requestShareOfInventoryByCategory.png'

# Horizontal bars sorted so the highest share sits on top; long names stay readable
ratios = groupedTable['proportion of requests/inventory'].sort_values(ascending=True)

fig, ax = plt.subplots(figsize=(10, 7), dpi=150)
bars = ax.barh(ratios.index, ratios.values, color='#2a78d6', height=0.72)

# Reference line where request lines equal starting stock
ax.axvline(100, color='#898781', linewidth=1, linestyle=(0, (4, 3)))
ax.text(100, len(ratios) - 0.15, ' 100% of inventory', color='#898781', fontsize=8, va='bottom')

# Direct value label at the end of every bar, in text ink rather than series color
ax.bar_label(bars, padding=4, fontsize=9, color='#52514e', fmt='%.0f%%')

ax.set_title(plotTitle, loc='left', fontsize=14, fontweight='bold', color='#0b0b0b', pad=12)
ax.set_xlabel('Request lines / initial inventory', color='#52514e')
ax.set_ylabel('')
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f'{value:.0f}%'))

# Recessive chrome: hairline vertical grid, no top/right spines, muted ticks
ax.xaxis.grid(True, color='#e1e0d9', linewidth=0.8)
ax.set_axisbelow(True)
for side in ('top', 'right'):
    ax.spines[side].set_visible(False)
for side in ('left', 'bottom'):
    ax.spines[side].set_color('#c3c2b7')
ax.tick_params(axis='x', colors='#898781', length=3)
ax.tick_params(axis='y', colors='#0b0b0b', length=0)
ax.set_xlim(0, ratios.max() * 1.12)  # headroom for the end labels
ax.set_ylim(-0.6, len(ratios) + 0.4)  # room above the top bar for the reference-line label

fig.patch.set_facecolor('#fcfcfb')
ax.set_facecolor('#fcfcfb')
fig.tight_layout()
fig.savefig(outputPath)
plt.show()
