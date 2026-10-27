# Cal Hacks 13.0 Hardware Checkout Analysis

An exploration of the hardware checkout system used at Cal Hacks 13.0 (October 23–25, 2026). The goal is to understand how hackers actually requested and used hardware so the next hackathon can run the lending desk more efficiently, stock it more accurately, and give hackers a better experience.

## Data

| File | What it holds |
|---|---|
| `rawData/calhacks13_hardware_requests.csv` | One row per request: who, when, status, and the items list |
| `rawData/calhacks13_hardware_items.csv` | One row per unit requested, with item name and category |
| `rawData/calhacks13_hardware_initial_inventory.csv` | Starting stock per item and category |
| `cleanedData/` | Outputs of the duplicate-order pass (see below) |

## Findings so far

### Demand is front-loaded and follows the working day

Requests spike in the first hour after checkout opens on Friday evening and stay elevated through the rest of that night. On Saturday, demand rises again through the daytime working hours and falls off overnight. Almost nothing is requested on Sunday morning.

![Hardware requests per hour across the event](visualizations/checkoutTimedistribution.png)

For the desk, this means the heaviest staffing and the most pre-staged kits are needed in the opening hours, with a second, smaller push during Saturday daytime.

### Several categories were requested more than we stocked

Comparing request lines against the initial inventory, four categories were oversubscribed: boards, peripherals, Cal Hacks Arduino kits, and sensors. Boards were requested almost three times as often as there were boards to lend.

![Request lines as a share of initial inventory by category](visualizations/requestShareOfInventoryByCategory.png)

Bulk components such as resistors, capacitors, and wires were heavily overstocked relative to requests. Shifting budget from those toward boards, kits, peripherals, and sensors is the clearest inventory change for next year.

Note that the request side counts request lines, not units, so demand for bulk parts is understated. The direction of the finding holds either way.

## Scripts

All scripts run from the repository root and read from `rawData/`.

| Script | Purpose |
|---|---|
| `analysisScripts/initial_exploration.py` | Hourly histogram of request times; `plotData` and `binMinutes` control the subset and granularity |
| `analysisScripts/explore_means.py` | Average units per request over time bins |
| `analysisScripts/hardware_mapping.py` | Requests versus initial inventory per category, grouped bars |
| `analysisScripts/hardware_iventory_request_comparison.py` | Requests as a percentage of initial inventory per category |
| `analysisScripts/clean_data.py` | Flags duplicate orders (same hacker, same or subset parts, within a short window) and writes a deduplicated request table |

Install dependencies with `pip install -r requirements.txt`, then for example:

```
python analysisScripts/initial_exploration.py
python analysisScripts/clean_data.py --window 20 --rule exact
```

## Open questions

- How much of the first-hour spike is duplicate or speculative ordering versus real demand? The duplicate pass in `clean_data.py` is the first step toward answering this.
- How long did hackers hold items, and did any categories run dry mid-event rather than just on paper?
- Do cancelled requests cluster around items that were out of stock at the time?
