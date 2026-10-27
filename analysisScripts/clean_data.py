"""Flag duplicate hardware orders.

A pair of requests is treated as a duplicate when all three hold:
  1. Same hacker (matched on normalized email).
  2. Placed within WINDOW_MINUTES of each other.
  3. One request's parts are the same as, or a subset of, the other's.
     Parts are compared as multisets, so "Dupont wire x2" is not a subset of
     "Dupont wire x1" but is a subset of "Dupont wire x3".

Outputs:
  * duplicate_requests.csv - every duplicate pair, with a shared duplicate_group id
  * unique_requests.csv    - every request with duplicates collapsed to one row per group
    (the kept row is the non-cancelled request if there is one, otherwise the latest)

Run from the repo root:
    python analysisScripts/clean_data.py
    python analysisScripts/clean_data.py --window 15 --rule exact
"""

import argparse
import os
from collections import Counter

import pandas as pd

REQUESTS_PATH = 'rawData/calhacks13_hardware_requests.csv'
ITEMS_PATH = 'rawData/calhacks13_hardware_items.csv'
OUTPUT_PATH = 'cleanedData/duplicate_requests.csv'
UNIQUE_OUTPUT_PATH = 'cleanedData/unique_requests.csv'

WINDOW_MINUTES = 20   # how close in time two orders must be to count as duplicates
MATCH_RULE = 'exact'  # 'subset' = same or subset of parts either way; 'exact' = identical parts only


def load_requests_with_parts(requestsPath: str, itemsPath: str) -> pd.DataFrame:
    """One row per request, with a Counter of its parts built from the items file."""
    requests = pd.read_csv(requestsPath, parse_dates=['requested_at_pt'])
    items = pd.read_csv(itemsPath)

    # items CSV has one row per unit, so a list of item names is already a multiset
    partsByRequest = items.groupby('request_id')['item_name'].agg(list).map(Counter)
    requests['parts'] = requests['request_id'].map(partsByRequest)

    missing = requests['parts'].isna().sum()
    if missing:
        raise ValueError(f'{missing} requests have no rows in the items file')

    requests['hacker_key'] = requests['hacker_email'].str.strip().str.lower()
    return requests.sort_values(['hacker_key', 'requested_at_pt']).reset_index(drop=True)


def classify_pair(earlierParts: Counter, laterParts: Counter) -> str | None:
    """Return how the two part lists relate, or None if neither contains the other."""
    if earlierParts == laterParts:
        return 'identical'
    if laterParts <= earlierParts:
        return 'later is subset of earlier'
    if earlierParts <= laterParts:
        return 'earlier is subset of later'
    return None


def find_duplicate_pairs(requests: pd.DataFrame, windowMinutes: int, rule: str) -> pd.DataFrame:
    window = pd.Timedelta(minutes=windowMinutes)
    pairs = []

    for _, group in requests.groupby('hacker_key', sort=False):
        rows = group.to_dict('records')
        for a, earlier in enumerate(rows):
            for later in rows[a + 1:]:
                gap = later['requested_at_pt'] - earlier['requested_at_pt']
                if gap > window:
                    break  # rows are time-sorted, so nothing further is within the window
                relation = classify_pair(earlier['parts'], later['parts'])
                if relation is None or (rule == 'exact' and relation != 'identical'):
                    continue
                pairs.append({
                    'hacker_name': earlier['hacker_name'],
                    'hacker_email': earlier['hacker_email'],
                    'earlier_request_id': earlier['request_id'],
                    'earlier_requested_at': earlier['requested_at_pt'],
                    'earlier_status': earlier['request_status'],
                    'earlier_items': earlier['items'],
                    'later_request_id': later['request_id'],
                    'later_requested_at': later['requested_at_pt'],
                    'later_status': later['request_status'],
                    'later_items': later['items'],
                    'gap_minutes': round(gap.total_seconds() / 60, 1),
                    'relation': relation,
                })

    return pd.DataFrame(pairs)


def assign_duplicate_groups(pairs: pd.DataFrame) -> pd.DataFrame:
    """Chain overlapping pairs (A~B, B~C) into one group id so a triple re-order is one group."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for earlierId, laterId in zip(pairs['earlier_request_id'], pairs['later_request_id']):
        parent[find(earlierId)] = find(laterId)

    roots = pairs['earlier_request_id'].map(find)
    groupIds = {root: n + 1 for n, root in enumerate(roots.drop_duplicates())}
    pairs.insert(0, 'duplicate_group', roots.map(groupIds))
    return pairs


STATUS_PRIORITY = {'returned': 0, 'checked_out': 1, 'reserved': 2, 'cancelled': 3}


def build_unique_requests(requests: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    """All requests with each duplicate group collapsed to a single kept row.

    Within a group the kept request is the one that progressed furthest
    (returned > checked_out > reserved > cancelled); ties go to the latest order.
    duplicate_group is filled for kept rows that absorbed duplicates, blank otherwise.
    """
    unique = requests.drop(columns=['parts', 'hacker_key']).copy()
    if pairs.empty:
        unique['duplicate_group'] = pd.NA
        return unique.sort_values('requested_at_pt').reset_index(drop=True)

    groupByRequest = pd.concat([
        pairs.set_index('earlier_request_id')['duplicate_group'],
        pairs.set_index('later_request_id')['duplicate_group'],
    ])
    groupByRequest = groupByRequest[~groupByRequest.index.duplicated()]
    unique['duplicate_group'] = unique['request_id'].map(groupByRequest).astype('Int64')

    unique['_statusRank'] = unique['request_status'].map(STATUS_PRIORITY).fillna(len(STATUS_PRIORITY))
    unique = unique.sort_values(['_statusRank', 'requested_at_pt'], ascending=[True, False])

    inGroup = unique['duplicate_group'].notna()
    keptInGroup = unique[inGroup].drop_duplicates('duplicate_group', keep='first')
    unique = pd.concat([unique[~inGroup], keptInGroup])

    return (unique.drop(columns='_statusRank')
                  .sort_values('requested_at_pt')
                  .reset_index(drop=True))


def main():
    parser = argparse.ArgumentParser(description='Flag duplicate hardware orders.')
    parser.add_argument('--window', type=int, default=WINDOW_MINUTES, help='time window in minutes')
    parser.add_argument('--rule', choices=['subset', 'exact'], default=MATCH_RULE, help='how parts must match')
    parser.add_argument('--output', default=OUTPUT_PATH, help='where to write the duplicate pairs CSV')
    parser.add_argument('--unique-output', default=UNIQUE_OUTPUT_PATH, help='where to write the deduplicated requests CSV')
    args = parser.parse_args()

    requests = load_requests_with_parts(REQUESTS_PATH, ITEMS_PATH)
    pairs = find_duplicate_pairs(requests, args.window, args.rule)

    if not pairs.empty:
        pairs = assign_duplicate_groups(pairs)
        pairs = pairs.sort_values(['duplicate_group', 'earlier_requested_at']).reset_index(drop=True)

    unique = build_unique_requests(requests, pairs)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    os.makedirs(os.path.dirname(args.unique_output), exist_ok=True)
    pairs.to_csv(args.output, index=False)
    unique.to_csv(args.unique_output, index=False)

    if pairs.empty:
        print(f'No duplicate orders found within {args.window} minutes using rule "{args.rule}".')
        print(f'All {len(unique)} requests written to {args.unique_output}')
        return

    flaggedRequests = set(pairs['earlier_request_id']) | set(pairs['later_request_id'])
    print(f'Window: {args.window} min, rule: {args.rule}')
    print(f'Duplicate pairs:    {len(pairs)}')
    print(f'Duplicate groups:   {pairs["duplicate_group"].nunique()}')
    print(f'Requests involved:  {len(flaggedRequests)} of {len(requests)}')
    print(f'Unique requests:    {len(unique)} ({len(requests) - len(unique)} duplicates dropped)')
    print(f'Hackers involved:   {pairs["hacker_email"].nunique()}')
    print('\nBy relation:')
    print(pairs['relation'].value_counts().to_string())
    print('\nStatus of the earlier request in each pair:')
    print(pairs['earlier_status'].value_counts().to_string())
    print(f'\nDuplicate pairs written to {args.output}')
    print(f'Unique requests written to {args.unique_output}')


if __name__ == '__main__':
    main()
