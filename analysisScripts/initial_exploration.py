from datetime import datetime, date

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DATA_PATH = 'rawData/calhacks13_hardware_requests.csv'

hardwareRequests = pd.read_csv(DATA_PATH)

checkedOutTimes = hardwareRequests['requested_at_pt'].apply(lambda timestamp_str: datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"))
checkOutDayOne = checkedOutTimes[checkedOutTimes < pd.Timestamp(date(2026, 10, 24))]
checkOutDayTwo = checkedOutTimes[pd.Timestamp(date(2026, 10, 24)) < checkedOutTimes][checkedOutTimes < pd.Timestamp(date(2026, 10, 25))]
# checkedOutTimesConverted = [datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S") for timestamp_str in checkedOutTimesRaw]

# print(hardwareRequests.head())

# print(checkedOutTimes)

# ---- Swap the data being visualized here ------------------------------------
# plotData must be a Series of timestamps (e.g. checkedOutTimes, checkOutDayOne)
plotData = checkOutDayTwo
binMinutes = 15  # width of each bar; e.g. 60 for hourly, 15 for quarter-hour granularity
plotTitle = 'Hardware requests per quarter-hour, Cal Hacks 13.0 (Oct 24, 2026)'
outputPath = 'visualizations/checkoutTimedistributionDayTwo.png'
# -----------------------------------------------------------------------------

# Bins of binMinutes spanning the plotted range, aligned to the clock
binFreq = pd.Timedelta(minutes=binMinutes)
binStart = plotData.min().floor(binFreq)
binEnd = plotData.max().ceil(binFreq)
timeBins = pd.date_range(binStart, binEnd, freq=binFreq)

fig, ax = plt.subplots(figsize=(11, 5), dpi=150)
ax.hist(
    plotData,
    bins=timeBins,
    color='#2a78d6',
    edgecolor='#fcfcfb',  # 2px surface gap between adjacent bars
    linewidth=1,
)

ax.set_title(plotTitle, loc='left', fontsize=14, fontweight='bold', color='#0b0b0b', pad=12)
ax.set_xlabel('Request time (PT)', color='#52514e')
ax.set_ylabel('Requests', color='#52514e')

# Date axis: major tick spacing adapts to the plotted span; minor ticks sit on bin edges
spanHours = (binEnd - binStart) / pd.Timedelta(hours=1)
if spanHours <= 3:
    majorLocator = mdates.MinuteLocator(byminute=[0, 15, 30, 45])
elif spanHours <= 12:
    majorLocator = mdates.HourLocator()
else:
    majorLocator = mdates.HourLocator(byhour=[0, 6, 12, 18])
ax.xaxis.set_major_locator(majorLocator)
ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(majorLocator, show_offset=False))
ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=binMinutes) if binMinutes < 60 else mdates.HourLocator())

# Recessive chrome: hairline horizontal grid, no top/right spines, muted ticks
ax.yaxis.grid(True, color='#e1e0d9', linewidth=0.8)
ax.set_axisbelow(True)
for side in ('top', 'right'):
    ax.spines[side].set_visible(False)
for side in ('left', 'bottom'):
    ax.spines[side].set_color('#c3c2b7')
ax.tick_params(colors='#898781', length=3)
ax.set_xlim(binStart, binEnd)
ax.margins(y=0.05)

fig.patch.set_facecolor('#fcfcfb')
ax.set_facecolor('#fcfcfb')
fig.tight_layout()
fig.savefig(outputPath)