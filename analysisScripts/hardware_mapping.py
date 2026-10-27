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
groupedRequests = hardwareTypeRequests.groupby('item_category', observed=False).aggregate({'item_category': 'count'})
groupedInventory = hardwareTypeInventory.groupby('category', observed=False).aggregate({'initial_quantity': 'sum'})
# print(groupedRequests.head())

# ---- Plot --------------------------------------------------------------------
plotTitle = 'Hardware requested vs. initial inventory by category, Cal Hacks 13.0'
outputPath = 'visualizations/requestsVsInventoryByCategory.png'

# Join the two aggregates on category; categories with no requests (e.g. '(none)') drop out.
comparison = pd.DataFrame({
    'Request lines': groupedRequests['item_category'],
    'Initial inventory': groupedInventory['initial_quantity'],
}).dropna(subset=['Request lines']).fillna(0)
comparison = comparison.sort_values('Request lines', ascending=True)  # largest ends up on top

seriesColors = {'Request lines': '#2a78d6', 'Initial inventory': '#eb6834'}
barHeight = 0.38
yPositions = range(len(comparison))

fig, ax = plt.subplots(figsize=(11, 8), dpi=150)
requestBars = ax.barh(
    [y + barHeight / 2 for y in yPositions], comparison['Request lines'],
    height=barHeight - 0.04, color=seriesColors['Request lines'], label='Request lines',
)
inventoryBars = ax.barh(
    [y - barHeight / 2 for y in yPositions], comparison['Initial inventory'],
    height=barHeight - 0.04, color=seriesColors['Initial inventory'], label='Initial inventory',
)

# Direct value labels in text ink, not series color
ax.bar_label(requestBars, padding=4, fontsize=8, color='#52514e', fmt='%d')
ax.bar_label(inventoryBars, padding=4, fontsize=8, color='#52514e', fmt='%d')

ax.set_yticks(list(yPositions))
ax.set_yticklabels(comparison.index)
ax.set_title(plotTitle, loc='left', fontsize=14, fontweight='bold', color='#0b0b0b', pad=12)
ax.set_xlabel('Count', color='#52514e')
ax.set_ylabel('')
ax.legend(loc='lower right', frameon=False, labelcolor='#52514e')

# Recessive chrome: hairline vertical grid, no top/right spines, muted ticks
ax.xaxis.grid(True, color='#e1e0d9', linewidth=0.8)
ax.set_axisbelow(True)
for side in ('top', 'right'):
    ax.spines[side].set_visible(False)
for side in ('left', 'bottom'):
    ax.spines[side].set_color('#c3c2b7')
ax.tick_params(axis='x', colors='#898781', length=3)
ax.tick_params(axis='y', colors='#0b0b0b', length=0)
ax.set_xlim(0, comparison.values.max() * 1.08)  # headroom for the end labels
ax.margins(y=0.01)

fig.patch.set_facecolor('#fcfcfb')
ax.set_facecolor('#fcfcfb')
fig.tight_layout()
fig.savefig(outputPath)
plt.show()
