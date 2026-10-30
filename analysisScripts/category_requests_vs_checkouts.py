"""
Cumulative units requested versus units actually checked out, per hardware
category, hour by hour across the event.

Each row of hardware_items.csv is one unit. A unit counts as requested in the
hour of its request (requested_at_pt), whatever happened to it afterwards, and
as checked out in the hour it was handed over (checked_out_at_pt). The gap
between the two curves is demand the desk never filled: units cancelled or
reserved but never picked up. Each panel also marks the category's initial
stock so both curves can be read against what was available.

By default the requested side is limited to the deduplicated requests in
unique_requests.csv (see clean_data.py), so a hacker who re-ordered the same
parts is not counted twice. The checked-out side always uses every unit that
left the desk, including units on a request the dedupe pass folded away.

Run from the repository root:  python analysisScripts/category_requests_vs_checkouts.py
"""
import math

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATA_PATH_CHECKED_OUT = 'cleanedData/hardware_items.csv'
DATA_PATH_INIT = "cleanedData/hardware_initial_inventory.csv"
DATA_PATH_UNIQUE_REQUESTS = 'cleanedData/unique_requests.csv'

# ---- Swap the categories being analysed here --------------------------------
# Any item_category value from hardware_items.csv; one panel is drawn per category.
categories = ['Boards', 'Peripherals', 'Cal Hacks Arduino Kit', 'Sensors']
binMinutes = 60
dedupeRequests = True  # count requested units from unique_requests.csv only
plotTitle = 'Units requested vs. checked out by category, Cal Hacks 13.0'
outputPath = 'visualizations/hardwareDistributions/requestsVsCheckoutsOverTimeByCategory.png'
# -----------------------------------------------------------------------------

hardwareUnits = pd.read_csv(DATA_PATH_CHECKED_OUT)
hardwareInventory = pd.read_csv(DATA_PATH_INIT)

for column in ('requested_at_pt', 'checked_out_at_pt'):
    hardwareUnits[column] = pd.to_datetime(hardwareUnits[column], format="%Y-%m-%d %H:%M:%S")

knownCategories = set(hardwareUnits['item_category'].dropna())
unknown = [c for c in categories if c not in knownCategories]
if unknown:
    raise SystemExit(f'Unknown categories {unknown}. Choose from: {sorted(knownCategories)}')

inventoryByCategory = hardwareInventory.groupby('category')['initial_quantity'].sum()

# Hourly bins from the first request to the last checkout, aligned to the clock
binFreq = pd.Timedelta(minutes=binMinutes)
binStart = hardwareUnits['requested_at_pt'].min().floor(binFreq)
binEnd = max(hardwareUnits['requested_at_pt'].max(), hardwareUnits['checked_out_at_pt'].max()).ceil(binFreq)
timeBins = pd.date_range(binStart, binEnd, freq=binFreq)

selected = hardwareUnits[hardwareUnits['item_category'].isin(categories)]

# Requested side: drop the later copies of duplicate orders. Checkouts are never
# filtered, because a unit handed over on a folded-away request still left the desk.
requested = selected
if dedupeRequests:
    uniqueIds = set(pd.read_csv(DATA_PATH_UNIQUE_REQUESTS)['request_id'])
    requested = selected[selected['request_id'].isin(uniqueIds)]
    print(f'{len(selected) - len(requested)} units on duplicate requests excluded from the requested side')


def unitsPerBin(frame, column):
    """Units per (hour bin, category) for the frame's event timestamps; NaT rows are ignored."""
    events = frame.assign(time_bin=pd.cut(frame[column], bins=timeBins, right=False)).dropna(subset=['time_bin'])
    table = (
        events.groupby(['time_bin', 'item_category'], observed=False)
        .size()
        .unstack('item_category')
        .reindex(columns=categories, fill_value=0)
    )
    table.index = table.index.categories.left  # bin start timestamps
    return table


cumulativeRequested = unitsPerBin(requested, 'requested_at_pt').cumsum()
cumulativeCheckedOut = unitsPerBin(selected, 'checked_out_at_pt').cumsum()

statusCounts = requested.groupby(['item_category', 'item_status']).size().unstack(fill_value=0).reindex(categories, fill_value=0)
summary = pd.DataFrame({
    'initial_inventory': inventoryByCategory[categories].astype(int),
    'units_requested': cumulativeRequested.iloc[-1].astype(int),
    'units_checked_out': cumulativeCheckedOut.iloc[-1].astype(int),
    'cancelled': statusCounts.get('cancelled', 0),
    'reserved_never_picked_up': statusCounts.get('reserved', 0),
})
summary['fill_rate'] = (summary['units_checked_out'] / summary['units_requested']).map('{:.0%}'.format)
if dedupeRequests:
    print('Requested, cancelled and reserved counts use deduplicated requests; checked out uses every unit.')
print(summary.to_string())

# ---- Plot --------------------------------------------------------------------
seriesColors = {'Units requested': '#2a78d6', 'Units checked out': '#eb6834'}
nCols = 2 if len(categories) > 1 else 1
nRows = math.ceil(len(categories) / nCols)

fig, axes = plt.subplots(nRows, nCols, figsize=(11, 3.4 * nRows + 0.8), dpi=150, sharex=True, squeeze=False)
plotIndex = cumulativeRequested.index.append(pd.DatetimeIndex([binEnd]))

for ax, category in zip(axes.flat, categories):
    for label, table in (('Units requested', cumulativeRequested), ('Units checked out', cumulativeCheckedOut)):
        values = table[category]
        # Step line: the running total only changes when a unit is requested or handed over
        ax.step(plotIndex, list(values) + [values.iloc[-1]], where='post',
                color=seriesColors[label], linewidth=2, label=label)
        ax.annotate(f'{values.iloc[-1]:d}', xy=(binEnd, values.iloc[-1]), xytext=(4, 0),
                    textcoords='offset points', va='center', fontsize=8, color='#52514e')

    # Reference line at the category's starting stock
    stock = inventoryByCategory[category]
    ax.axhline(stock, color='#898781', linewidth=1, linestyle=(0, (4, 3)))
    ax.text(binStart, stock, f'  initial stock {stock:.0f}', color='#898781', fontsize=8, va='bottom')

    ax.set_title(category, loc='left', fontsize=11, fontweight='bold', color='#0b0b0b', pad=6)
    ax.set_ylim(0, max(cumulativeRequested[category].max(), stock) * 1.15)
    ax.set_xlim(binStart, binEnd + (binEnd - binStart) * 0.05)  # room for the end labels

    # Recessive chrome: hairline horizontal grid, no top/right spines, muted ticks
    ax.yaxis.grid(True, color='#e1e0d9', linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color('#c3c2b7')
    ax.tick_params(colors='#898781', length=3, labelsize=8)
    ax.set_facecolor('#fcfcfb')

for ax in axes.flat[len(categories):]:
    ax.set_visible(False)  # unused panel when the category count is odd

majorLocator = mdates.HourLocator(byhour=[0, 12])
for ax in axes[-1]:
    ax.xaxis.set_major_locator(majorLocator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(majorLocator, show_offset=False))
    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 18]))
    ax.set_xlabel('Time (PT)', color='#52514e', fontsize=9)
for ax in axes[:, 0]:
    ax.set_ylabel('Cumulative units', color='#52514e', fontsize=9)

handles, labels = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='upper right', ncol=2, frameon=False, labelcolor='#52514e', bbox_to_anchor=(0.99, 0.985))
fig.suptitle(plotTitle, x=0.02, ha='left', fontsize=14, fontweight='bold', color='#0b0b0b')

fig.patch.set_facecolor('#fcfcfb')
fig.tight_layout(rect=(0, 0, 1, 0.95))
fig.savefig(outputPath)
plt.show()
