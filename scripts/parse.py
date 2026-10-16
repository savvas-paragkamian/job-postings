"""Step 2: read the saved answers back into one table of postings.

    python3 scripts/parse.py [YYYY-MM-DD]

Reads data/raw/<date>/fetch.csv and the files it lists; writes data/postings/<date>.csv,
one row per distinct posting (common.FIELDS), not yet scored. The same posting found
twice (two queries, or two platforms) is one row: rows merge when they share a uid,
or when two platforms list the same title (common.same_posting).
The first platform in the config wins a field; empty fields are filled from the others.
"""
from collections import Counter, defaultdict

import sources
from common import (FIELDS, ROOT, SUMMARY_CHARS, load_config, raw_dir, read_csv, run_date, same_posting, say,
                    title_key, write_csv)


def merge(into, row):
    for k in FIELDS:
        if not into[k] and row[k]:
            into[k] = row[k]
    names = into["sources"].split("; ") + [s for s in row["sources"].split("; ") if s not in into["sources"].split("; ")]
    into["sources"] = "; ".join(names)


def main():
    cfg, date = load_config(), run_date()
    by_id = {s["id"]: s for s in cfg["sources"]}
    order = {s["id"]: i for i, s in enumerate(cfg["sources"])}
    log = read_csv(raw_dir(date) / "fetch.csv")
    if not log:
        raise SystemExit(f"no data/raw/{date}/fetch.csv: run scripts/fetch.py {date} first")

    rows, read = [], Counter()
    for rec in sorted(log, key=lambda r: order.get(r["source"], 99)):
        src = by_id.get(rec["source"])
        if not src or rec["status"] != "ok":
            continue
        body = (raw_dir(date) / rec["file"]).read_bytes()
        for item in getattr(sources, "parse_" + src["type"])(body, src, date):
            item.update(kind=src["kind"], sources=src["id"], summary=item["summary"][:SUMMARY_CHARS])
            rows.append(item)
            read[src["id"]] += 1

    postings, by_uid, by_title = [], {}, defaultdict(list)
    for row in rows:
        target = by_uid.get(row["uid"]) or next((t for t in by_title[title_key(row)] if same_posting(t, row)), None)
        if target:
            merge(target, row)
        else:
            postings.append(row)
            by_title[title_key(row)].append(row)
            target = row
        by_uid.setdefault(row["uid"], target)

    out = ROOT / "data" / "postings" / f"{date}.csv"
    write_csv(out, postings, FIELDS)
    say(", ".join(f"{sid} {n}" for sid, n in read.items()) + " postings read")
    say(f"{len(rows)} postings read, {len(postings)} distinct; wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
