from datetime import datetime, date

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

TEAM_DATA_PATH = 'cleanedData/checked_in_hackers_teams.csv'
REQUESTS_DATA_PATH = 'cleanedData/unique_requests.csv'

hardwareRequests = pd.read_csv(REQUESTS_DATA_PATH)
hardwareRequests['requested_at_pt'] = hardwareRequests['requested_at_pt'].apply(lambda timestamp_str: datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"))

teamData = pd.read_csv(TEAM_DATA_PATH)
# A few checked-in names belong to two people and share a hacker_id; joining them
# would duplicate those requests, so they are left out of the team analysis.
teamData = teamData[teamData['name_ambiguous'] == 'no']

teamsAndNames = teamData[["hacker_id", "project_title", "hardware_hack"]]

# Inner join keeps requests from checked-in hackers; those with no Devpost project
# have no project_title / hardware_hack and drop out of the per-team groupings.
hardwareRequests = pd.merge(hardwareRequests, teamsAndNames, 'inner', 'hacker_id')
# print(hardwareRequests.head())

hardwareRequestsHardwareHack = hardwareRequests['hardware_hack'] == 'yes'

requestsAggregated = hardwareRequests.groupby('project_title', observed = False).agg(hardware_hack=('hardware_hack', 'first'), request_count=('project_title', 'count'))

# print(requestsAggregated)

hardwareHackAggregated = requestsAggregated.groupby('hardware_hack', observed=False).agg(hack_count=('hardware_hack', 'count'), request_count=('request_count', 'sum'))
hardwareHackAggregated['average_request_per_team'] = hardwareHackAggregated['request_count'] / hardwareHackAggregated['hack_count']
print(hardwareHackAggregated)

# ---- Shared styling ----------------------------------------------------------
SURFACE = '#fcfcfb'
INK, INK_SECONDARY, INK_MUTED = '#0b0b0b', '#52514e', '#898781'
GRID, SPINE = '#e1e0d9', '#c3c2b7'
# Fixed categorical slots: hardware hacks are always blue, the rest always orange
groupLabels = {'yes': 'Hardware hack', 'no': 'Not a hardware hack'}
groupColors = {'yes': '#2a78d6', 'no': '#eb6834'}
groupOrder = ['yes', 'no']


def styleAxes(ax, gridAxis='y'):
    """Recessive chrome shared by every figure: hairline grid, no top/right spines, muted ticks."""
    getattr(ax, f'{gridAxis}axis').grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(SPINE)
    ax.tick_params(colors=INK_MUTED, length=3)
    ax.set_facecolor(SURFACE)


def finishFigure(fig, ax, title, outputPath):
    ax.set_title(title, loc='left', fontsize=14, fontweight='bold', color=INK, pad=12)
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(outputPath)


# ---- 1. Request times, hardware hacks vs the rest (overlaid histogram) -------
binMinutes = 60
binFreq = pd.Timedelta(minutes=binMinutes)
allTimes = hardwareRequests['requested_at_pt']
binStart, binEnd = allTimes.min().floor(binFreq), allTimes.max().ceil(binFreq)
timeBins = pd.date_range(binStart, binEnd, freq=binFreq)

fig, ax = plt.subplots(figsize=(11, 5), dpi=150)
for key in groupOrder:
    times = hardwareRequests.loc[hardwareRequests['hardware_hack'] == key, 'requested_at_pt']
    ax.hist(times, bins=timeBins, alpha=0.55, color=groupColors[key], label=groupLabels[key], edgecolor='none')

ax.set_xlabel('Request time (PT)', color=INK_SECONDARY)
ax.set_ylabel('Requests per hour', color=INK_SECONDARY)
majorLocator = mdates.HourLocator(byhour=[0, 6, 12, 18])
ax.xaxis.set_major_locator(majorLocator)
ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(majorLocator, show_offset=False))
ax.xaxis.set_minor_locator(mdates.HourLocator())
ax.set_xlim(binStart, binEnd)
ax.margins(y=0.05)
styleAxes(ax, gridAxis='y')
ax.legend(frameon=False, loc='upper right', labelcolor=INK_SECONDARY)
finishFigure(fig, ax, 'Hardware requests per hour by project type, Cal Hacks 13.0', 'visualizations/requestTimesByHardwareHack.png')

# ---- 2. Share of requesting teams that were hardware hacks -------------------
# Two-slice pies are hard to read precisely, so this is a single 100% bar with
# the counts labelled directly on each segment.
teamCounts = hardwareHackAggregated['hack_count'].reindex(groupOrder)
teamTotal = teamCounts.sum()

fig, ax = plt.subplots(figsize=(10, 2.6), dpi=150)
left = 0
for key in groupOrder:
    share = teamCounts[key] / teamTotal
    ax.barh(0, share, left=left, color=groupColors[key], height=0.55, edgecolor=SURFACE, linewidth=2)
    ax.text(left + share / 2, 0, f'{groupLabels[key]}\n{teamCounts[key]} teams · {share:.0%}',
            ha='center', va='center', color=SURFACE, fontsize=10, fontweight='bold')
    left += share

ax.set_xlim(0, 1)
ax.set_ylim(-0.6, 0.6)
ax.set_yticks([])
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f'{value:.0%}'))
ax.set_xlabel(f'Share of the {teamTotal} teams that requested hardware', color=INK_SECONDARY)
styleAxes(ax, gridAxis='x')
ax.spines['left'].set_visible(False)
finishFigure(fig, ax, 'Teams that requested hardware, by project type', 'visualizations/hardwareHackTeamShare.png')

# ---- 3. Average requests per team ---------------------------------------------
averages = hardwareHackAggregated['average_request_per_team'].reindex(groupOrder)

fig, ax = plt.subplots(figsize=(7, 5), dpi=150)
bars = ax.bar([groupLabels[k] for k in groupOrder], averages.values,
              color=[groupColors[k] for k in groupOrder], width=0.6)
# Direct value label on each bar, in text ink rather than series color
ax.bar_label(bars, padding=4, fontsize=10, color=INK_SECONDARY, fmt='%.2f')

ax.set_ylabel('Requests per team', color=INK_SECONDARY)
ax.set_xlabel('')
ax.set_ylim(0, averages.max() * 1.15)  # headroom for the value labels
styleAxes(ax, gridAxis='y')
ax.tick_params(axis='x', colors=INK, length=0)
finishFigure(fig, ax, 'Average hardware requests per team by project type', 'visualizations/averageRequestsPerTeamByHardwareHack.png')

plt.show()
