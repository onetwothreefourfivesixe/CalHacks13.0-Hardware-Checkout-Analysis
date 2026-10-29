"""
Create a de-identified copy of the checked-in hackers / teams export.

rawData/calhacks13_checked_in_hackers_teams.csv has first_name / last_name but
no email, while rawData/name_mapping.csv (written by anonymize_data.py) keys
hackers on email. The bridge is the raw request/item exports, which carry both
hacker_name and hacker_email, so a checked-in hacker who made a hardware
request gets the same hacker_id used in cleanedData/hardware_requests.csv.

Everyone else gets a new hacker_id, numbered after the highest id already in
the mapping, in the order they appear in the export. Those new ids are
appended to name_mapping.csv (keyed on the full name, since there is no email)
so re-running the script is stable.

A handful of checked-in names belong to two different people (different
teams). If such a name also made a request, both rows receive the requester's
hacker_id and `name_ambiguous` is set to "yes"; otherwise each row gets its own
new id.

Output: cleanedData/checked_in_hackers_teams.csv with first_name/last_name
replaced by hacker_id.

Run from the repository root:  python analysisScripts/anonymize_checked_in.py
"""
import csv
import os
from collections import Counter

RAW_DIR = 'rawData'
OUT_DIR = 'cleanedData'
SRC = os.path.join(RAW_DIR, 'calhacks13_checked_in_hackers_teams.csv')
MAPPING = os.path.join(RAW_DIR, 'name_mapping.csv')
BRIDGE_FILES = ['calhacks13_hardware_requests.csv', 'calhacks13_hardware_items.csv']
DST = os.path.join(OUT_DIR, 'checked_in_hackers_teams.csv')
NAME_COLS = ('first_name', 'last_name')


def read(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
        return rows, (list(rows[0].keys()) if rows else [])


def write(path, rows, fieldnames):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def full_name(row):
    return ' '.join(row[c].strip() for c in NAME_COLS).strip().lower()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    mapping, map_cols = read(MAPPING)

    # 1. Existing ids. Hacker entries are emails (from anonymize_data.py) or
    #    full names (appended by earlier runs of this script).
    email_to_id, name_to_id = {}, {}
    for m in mapping:
        if m['kind'] != 'hacker':
            continue
        key = m['original'].strip().lower()
        (email_to_id if '@' in key else name_to_id)[key] = m['pseudonym']

    # 2. Bridge name -> email -> id through the raw request exports.
    requester_names = set()
    for src in BRIDGE_FILES:
        path = os.path.join(RAW_DIR, src)
        if not os.path.exists(path):
            print(f'warning: {path} missing, fewer names can be linked to request ids')
            continue
        for row in read(path)[0]:
            email = row.get('hacker_email', '').strip().lower()
            name = row.get('hacker_name', '').strip().lower()
            if name and email in email_to_id:
                name_to_id.setdefault(name, email_to_id[email])
                requester_names.add(name)

    next_num = 1 + max(
        (int(m['pseudonym'].split('_')[1]) for m in mapping if m['kind'] == 'hacker'),
        default=0,
    )

    # 3. Assign ids row by row.
    rows, cols = read(SRC)
    name_counts = Counter(full_name(r) for r in rows)
    new_mapping, out = [], []
    linked = 0
    for row in rows:
        name = full_name(row)
        ambiguous = name_counts[name] > 1
        # Duplicated names that did not request hardware are distinct people,
        # so key their mapping entry on name + project to keep them apart.
        key = name
        if ambiguous and name not in name_to_id:
            key = f"{name} | {row['project_title'].strip() or row['team_status'].strip()}".lower()
        if name in requester_names:
            hid = name_to_id[name]
            linked += 1
        elif key in name_to_id:
            hid = name_to_id[key]
        else:
            hid = f'hacker_{next_num:03d}'
            next_num += 1
            name_to_id[key] = hid
            new_mapping.append({'kind': 'hacker', 'original': key, 'pseudonym': hid})
        r = {'hacker_id': hid}
        r.update({c: row[c] for c in cols if c not in NAME_COLS})
        r['name_ambiguous'] = 'yes' if ambiguous and name in requester_names else 'no'
        out.append(r)

    new_cols = ['hacker_id'] + [c for c in cols if c not in NAME_COLS] + ['name_ambiguous']
    write(DST, out, new_cols)

    if new_mapping:
        with open(MAPPING, 'a', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=map_cols).writerows(new_mapping)

    flagged = sum(1 for r in out if r['name_ambiguous'] == 'yes')
    print(f'{SRC} -> {DST} ({len(out)} rows)')
    print(f'{linked} rows linked to an existing request hacker_id, '
          f'{len(new_mapping)} new ids appended to {MAPPING}, '
          f'{flagged} rows flagged name_ambiguous')


if __name__ == '__main__':
    main()
