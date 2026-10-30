"""
Share of each hardware category's initial inventory that was out on loan,
hour by hour across the event.

Each row of hardware_items.csv is one unit, so units are counted as rows. A
unit joins the loaned-out count in the hour it was handed over
(checked_out_at_pt) and leaves it again in the hour it came back
(returned_at_pt), so the curve is the net number of units out at the end of
each hour. Units never returned stay counted to the end. The denominator is the
category's summed initial_quantity from hardware_initial_inventory.csv.

Run from the repository root:  python analysisScripts/share_of_hardware_checked_out.py
"""
from datetime import datetime, date

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATA_PATH_CHECKED_OUT = 'cleanedData/hardware_items.csv'
DATA_PATH_INIT = "cleanedData/hardware_initial_inventory.csv"

# ---- Swap the categories being analysed here --------------------------------
# Any item_category value from hardware_items.csv. Up to four plot cleanly on
# one chart; the first four below are the categories requested beyond stock.
categories = ['Boards', 'Peripherals', 'Cal Hacks Arduino Kit', 'Sensors']
binMinutes = 60
plotTitle = 'Share of initial inventory out on loan by category, Cal Hacks 13.0'
outputPath = 'visualizations/hardwareDistributions/unitsOnLoanShareOverTimeByCategory.png'
# -----------------------------------------------------------------------------

hardwareUnits = pd.read_csv(DATA_PATH_CHECKED_OUT)
hardwareInventory = pd.read_csv(DATA_PATH_INIT)

for column in ('checked_out_at_pt', 'returned_at_pt'):
    hardwareUnits[column] = pd.to_datetime(hardwareUnits[column], format="%Y-%m-%d %H:%M:%S")
# Units that actually left the desk: item_status 'checked_out' (still out) or 'returned'
hardwareUnits = hardwareUnits[hardwareUnits['checked_out_at_pt'].notna()]

knownCategories = set(hardwareUnits['item_category'])
unknown = [c for c in categories if c not in knownCategories]
if unknown:
    raise SystemExit(f'Unknown categories {unknown}. Choose from: {sorted(knownCategories)}')

# Initial stock per category is the denominator for that category's share
inventoryByCategory = hardwareInventory.groupby('category')['initial_quantity'].sum()

# Hourly bins spanning first checkout to last return, aligned to the clock, shared by every category
binFreq = pd.Timedelta(minutes=binMinutes)
binStart = hardwareUnits['checked_out_at_pt'].min().floor(binFreq)
binEnd = max(hardwareUnits['checked_out_at_pt'].max(), hardwareUnits['returned_at_pt'].max()).ceil(binFreq)
timeBins = pd.date_range(binStart, binEnd, freq=binFreq)

selected = hardwareUnits[hardwareUnits['item_category'].isin(categories)]


def unitsPerBin(timestamps):
    """Units per (hour bin, category) for the given event timestamps; NaT rows are ignored."""
    events = selected.assign(time_bin=pd.cut(timestamps, bins=timeBins, right=False)).dropna(subset=['time_bin'])
    table = (
        events.groupby(['time_bin', 'item_category'], observed=False)
        .size()
        .unstack('item_category')
        .reindex(columns=categories, fill_value=0)
    )
    table.index = table.index.categories.left  # bin start timestamps
    return table


checkoutsPerBin = unitsPerBin(selected['checked_out_at_pt'])
returnsPerBin = unitsPerBin(selected['returned_at_pt'])

# Net units out at the end of each hour: everything handed over so far minus everything brought back
cumulativeCheckouts = checkoutsPerBin.cumsum()
cumulativeReturns = returnsPerBin.cumsum()
unitsOut = cumulativeCheckouts - cumulativeReturns
shareOut = unitsOut / inventoryByCategory[categories]

summary = pd.DataFrame({
    'initial_inventory': inventoryByCategory[categories].astype(int),
    'units_checked_out': cumulativeCheckouts.iloc[-1].astype(int),
    'units_returned': cumulativeReturns.iloc[-1].astype(int),
    'still_out_at_end': unitsOut.iloc[-1].astype(int),
    'peak_units_out': unitsOut.max().astype(int),
    'peak_share': shareOut.max().map('{:.1%}'.format),
    'peak_hour': unitsOut.idxmax().dt.strftime('%a %H:%M'),
})
print(summary.to_string())
print()
print(shareOut.to_string(float_format=lambda v: f'{v:.1%}'))

# ---- Plot --------------------------------------------------------------------
# Fixed categorical slots in list order, never cycled
seriesColors = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6']
if len(categories) > len(seriesColors):
    raise SystemExit(f'At most {len(seriesColors)} categories can be plotted at once')

fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
# Step line: the share only changes when a unit is handed over or returned, so hold each value across its hour
plotIndex = shareOut.index.append(pd.DatetimeIndex([binEnd]))
for category, color in zip(categories, seriesColors):
    values = shareOut[category]
    ax.step(plotIndex, list(values) + [values.iloc[-1]], where='post',
            color=color, linewidth=2, label=category)

# Direct labels at each line's end, in text ink; the colored line carries identity.
# Labels closer than minGap (in share units) are pushed apart so they stay legible.
minGap = 0.045
finals = shareOut.iloc[-1].sort_values()
labelY = list(finals.values)
for i in range(1, len(labelY)):
    labelY[i] = max(labelY[i], labelY[i - 1] + minGap)
for (category, share), y in zip(finals.items(), labelY):
    # x is offset in points from the line's end; y is the (possibly nudged) height in data units
    ax.annotate(f'{category}  {share:.0%}', xy=(binEnd, share), xytext=(6, y),
                textcoords=('offset points', 'data'), va='center', fontsize=9, color='#52514e')

ax.set_title(plotTitle, loc='left', fontsize=14, fontweight='bold', color='#0b0b0b', pad=12)
ax.set_xlabel('Time (PT)', color='#52514e')
ax.set_ylabel('Units out on loan / initial inventory', color='#52514e')
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f'{value:.0%}'))
ax.legend(loc='upper right', ncol=len(categories), frameon=False, labelcolor='#52514e')  # one row in the empty band above the curves

majorLocator = mdates.HourLocator(byhour=[0, 6, 12, 18])
ax.xaxis.set_major_locator(majorLocator)
ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(majorLocator, show_offset=False))
ax.xaxis.set_minor_locator(mdates.HourLocator())

# Recessive chrome: hairline horizontal grid, no top/right spines, muted ticks
ax.yaxis.grid(True, color='#e1e0d9', linewidth=0.8)
ax.set_axisbelow(True)
for side in ('top', 'right'):
    ax.spines[side].set_visible(False)
for side in ('left', 'bottom'):
    ax.spines[side].set_color('#c3c2b7')
ax.tick_params(colors='#898781', length=3)
ax.set_xlim(binStart, binEnd + (binEnd - binStart) * 0.16)  # room for the end labels
ax.set_ylim(0, max(1.0, shareOut.values.max() * 1.08))

fig.patch.set_facecolor('#fcfcfb')
ax.set_facecolor('#fcfcfb')
fig.tight_layout()
fig.savefig(outputPath)
plt.show()
