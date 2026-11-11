"""Step 1: ask every platform in config/profiles.toml and save the answers as received.

    python3 scripts/fetch.py [YYYY-MM-DD] [--only=euraxess,nature]

Writes data/raw/<date>/<source>__<query>__<page>.<ext>, one file per request,
the watched pages as data/raw/<date>/watch__<id>.html, and data/raw/<date>/fetch.csv:
one row per request with its URL, status, number of postings and seconds.
--only fetches some platforms again and keeps the other rows of fetch.csv.
"""
import re
import time

import sources
from common import ROOT, flag, http, load_config, raw_dir, read_csv, run_date, say, write_csv

LOG_FIELDS = ["source", "query", "page", "url", "status", "items", "seconds", "file"]


def queries_for(source, cfg):
    """The queries sent to a platform: its own `queries` if it has them (the category pages
    of a Madgex board), else those of the profiles of its kind, once each."""
    if "{query}" not in source["url"]:
        return [""]
    if "queries" in source:
        return source["queries"]
    out = []
    for p in cfg["profiles"]:
        if p["kind"] == source["kind"]:
            out += [q for q in p["queries"] if q.lower() not in map(str.lower, out)]
    return out


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "all"


def main():
    cfg, date, only = load_config(), run_date(), flag("only")
    out = raw_dir(date)
    out.mkdir(parents=True, exist_ok=True)
    log = [row for row in read_csv(out / "fetch.csv") if only and row["source"].removeprefix("watch:") not in only]
    delay = cfg["settings"].get("delay_seconds", 1)

    def get(source_id, query, page, request, parse_items, filename):
        url, data, headers = request
        t0 = time.time()
        status, body, err = http(url, cfg, data, headers)
        (out / filename).write_bytes(body)
        items, state = [], err or ("ok" if status == 200 else f"HTTP {status}")
        if status == 200 and parse_items:
            try:
                items = parse_items(body)
            except Exception as e:  # an answer the parser cannot read: the site may have changed
                state = f"unreadable: {type(e).__name__}: {e}"
        log.append(dict(source=source_id, query=query, page=page, url=url, status=state, items=len(items),
                        seconds=round(time.time() - t0, 1), file=filename))
        say(f"{source_id:<17} {query[:30]:<30} p{page}  {state[:40]:<6} {len(items):>3}")
        time.sleep(delay)
        return status == 200 and not state.startswith("unreadable"), items

    for src in cfg["sources"]:
        if not src.get("enabled", True) or (only and src["id"] not in only):
            continue
        request = getattr(sources, "request_" + src["type"])
        parse = getattr(sources, "parse_" + src["type"])
        for query in queries_for(src, cfg):
            seen = set()
            for page in range(1, src.get("pages", 1) + 1):
                name = f"{src['id']}__{slug(query)}__{page:02d}.{sources.EXTENSION[src['type']]}"
                ok, items = get(src["id"], query, page, request(src, query, page),
                                lambda body: parse(body, src, date), name)
                new = {i["uid"] for i in items} - seen
                seen |= new
                if not ok or not new:
                    break

    for w in cfg.get("watch", []):
        if not only or w["id"] in only:
            get(f"watch:{w['id']}", "", 1, (w["url"], None, {}), None, f"watch__{w['id']}.html")

    write_csv(out / "fetch.csv", log, LOG_FIELDS)
    failed = [r for r in log if r["status"] != "ok"]
    say(f"\n{len(log)} requests, {len(failed)} not ok; wrote {(out / 'fetch.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
