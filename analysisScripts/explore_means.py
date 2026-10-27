from datetime import datetime, date

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATA_PATH = 'cleanedData/hardware_requests.csv'

hardwareRequests = pd.read_csv(DATA_PATH)[['requested_at_pt', 'unit_count']]

binMinutes = 60
binFreq = pd.Timedelta(minutes=binMinutes)

hardwareRequests['requested_at_pt'] = pd.to_datetime(hardwareRequests['requested_at_pt'], format="%Y-%m-%d %H:%M:%S")

# Bin edges of binFreq spanning the data, aligned to the clock
binStart = hardwareRequests['requested_at_pt'].min().floor(binFreq)
binEnd = hardwareRequests['requested_at_pt'].max().ceil(binFreq)
bins = pd.date_range(start=binStart, end=binEnd, freq=binFreq)

# Categorize and group. observed=False keeps empty bins as NaN so the line breaks
# over gaps (e.g. overnight) instead of drawing a false connection across them.
hardwareRequests['time_bins'] = pd.cut(hardwareRequests['requested_at_pt'], bins=bins, right=False)
groupedMeans = hardwareRequests.groupby('time_bins', observed=False).aggregate({'unit_count': 'mean'})
groupedMeans['bin_mid'] = pd.IntervalIndex(groupedMeans.index.categories).mid[groupedMeans.index.codes]  # categorical of intervals -> timestamps

# ---- Plot --------------------------------------------------------------------
plotTitle = f'Average units per request, {binMinutes}-minute bins, Cal Hacks 13.0'
outputPath = 'visualizations/meanUnitCountOverTime.png'

fig, ax = plt.subplots(figsize=(11, 5), dpi=150)
ax.plot(
    groupedMeans['bin_mid'],
    groupedMeans['unit_count'],
    color='#2a78d6',
    linewidth=2,
    marker='o',
    markersize=3,
)

ax.set_title(plotTitle, loc='left', fontsize=14, fontweight='bold', color='#0b0b0b', pad=12)
ax.set_xlabel('Request time (PT)', color='#52514e')
ax.set_ylabel('Mean unit count per request', color='#52514e')

# Date axis: major tick spacing adapts to the plotted span
spanHours = (binEnd - binStart) / pd.Timedelta(hours=1)
if spanHours <= 3:
    majorLocator = mdates.MinuteLocator(byminute=[0, 15, 30, 45])
elif spanHours <= 12:
    majorLocator = mdates.HourLocator()
else:
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
ax.set_xlim(binStart, binEnd)
ax.set_ylim(bottom=0)

fig.patch.set_facecolor('#fcfcfb')
ax.set_facecolor('#fcfcfb')
fig.tight_layout()
fig.savefig(outputPath)
plt.show()