"""
Create de-identified copies of the raw CSVs in cleanedData/.

- hacker_name / hacker_email are replaced by a single stable `hacker_id`
  (hacker_001, hacker_002, ...) keyed on the lower-cased email.
- Staff/hacker action columns (claimed_by, checked_out_by, returned_by,
  cancelled_by) are mapped to the same hacker_id when the name matches a
  hacker, otherwise to staff_01, staff_02, ...
- The inventory file contains no personal data and is copied as-is.

The name -> pseudonym mapping is written to rawData/name_mapping.csv, which is
git-ignored, so the real names never enter the repository.

Run from the repository root:  python analysisScripts/anonymize_data.py
"""
import csv
import os

RAW_DIR = 'rawData'
OUT_DIR = 'cleanedData'

FILES = {
    'calhacks13_hardware_requests.csv': 'hardware_requests.csv',
    'calhacks13_hardware_items.csv': 'hardware_items.csv',
    'calhacks13_hardware_initial_inventory.csv': 'hardware_initial_inventory.csv',
}
ACTOR_COLS = ['claimed_by', 'checked_out_by', 'returned_by', 'cancelled_by']


def read(path):
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
        return rows, (list(rows[0].keys()) if rows else [])


def write(path, rows, fieldnames):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    tables = {src: read(os.path.join(RAW_DIR, src)) for src in FILES}

    # 1. Hackers: one id per email, assigned in order of first appearance.
    email_to_id, name_to_id = {}, {}
    for src in ('calhacks13_hardware_requests.csv', 'calhacks13_hardware_items.csv'):
        for row in tables[src][0]:
            email = row.get('hacker_email', '').strip().lower()
            if email and email not in email_to_id:
                email_to_id[email] = f'hacker_{len(email_to_id) + 1:03d}'
            name = row.get('hacker_name', '').strip().lower()
            if name and email:
                name_to_id.setdefault(name, email_to_id[email])

    # 2. Actors: reuse hacker id when the name belongs to a hacker, else staff id.
    actor_to_id = {}

    def actor_id(name):
        key = name.strip().lower()
        if not key:
            return ''
        if key in name_to_id:
            return name_to_id[key]
        if key not in actor_to_id:
            actor_to_id[key] = f'staff_{len(actor_to_id) + 1:02d}'
        return actor_to_id[key]

    for src, dst in FILES.items():
        rows, cols = tables[src]
        if 'hacker_email' in cols:
            new_cols = []
            for c in cols:
                if c == 'hacker_name':
                    new_cols.append('hacker_id')
                elif c != 'hacker_email':
                    new_cols.append(c)
            out = []
            for row in rows:
                r = {c: row[c] for c in cols if c not in ('hacker_name', 'hacker_email')}
                r['hacker_id'] = email_to_id[row['hacker_email'].strip().lower()]
                for c in ACTOR_COLS:
                    if c in r:
                        r[c] = actor_id(r[c])
                out.append(r)
            write(os.path.join(OUT_DIR, dst), out, new_cols)
        else:
            write(os.path.join(OUT_DIR, dst), rows, cols)
        print(f'{src} -> {OUT_DIR}/{dst} ({len(rows)} rows)')

    # 3. Mapping stays in the ignored rawData folder.
    mapping = [{'kind': 'hacker', 'original': e, 'pseudonym': i} for e, i in email_to_id.items()]
    mapping += [{'kind': 'staff', 'original': n, 'pseudonym': i} for n, i in actor_to_id.items()]
    write(os.path.join(RAW_DIR, 'name_mapping.csv'), mapping, ['kind', 'original', 'pseudonym'])
    print(f'{len(email_to_id)} hackers, {len(actor_to_id)} staff -> {RAW_DIR}/name_mapping.csv')


if __name__ == '__main__':
    main()
