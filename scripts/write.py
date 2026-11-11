"""Step 3: score, compare with what was seen before, and write the pages.

    python3 scripts/write.py [YYYY-MM-DD] [--no-notify]

Reads data/postings/<date>.csv, data/seen.csv and the watched pages that fetch.py saved.
Writes
  data/seen.csv          every posting ever fetched, with the first and last date it was seen
  data/watch/<id>.txt    each watched text as last seen; data/watch/changes.csv lists the changes
  data/runs.csv          the counts behind index.md
  digests/<date>.md      what was new on <date>, by profile
  open.md                everything still open, by profile, soonest deadline first
  index.md               one row per digest
and a desktop notification (Mac or Linux) when this run found something new.
Postings are scored here, with the config as it is now: after changing a keyword,
`python3 scripts/run.py --no-fetch` rewrites the day's pages from the saved answers.
"""
import difflib
import re
import shutil
import subprocess
import sys
from collections import defaultdict

from common import (FIELDS, ROOT, SEEN_FIELDS, Scorer, Terms, days_before, flag, load_config, page_lines,
                    raw_dir, read_csv, run_date, same_posting, say, title_key, write_csv)

WATCH = ROOT / "data" / "watch"
CHANGE_FIELDS = ["date", "id", "name", "url", "added", "removed"]
RUN_FIELDS = ["date", "postings", "calls", "listed", "changed"]


# --- seen.csv ----------------------------------------------------------------------

def update_seen(seen, postings, date):
    """Merge the day's postings into seen (a list of rows, changed in place). Returns the
    uids that were not there before. Today's text replaces older text where it has any."""
    by_uid, by_title = {r["uid"]: r for r in seen}, defaultdict(list)
    for r in seen:
        by_title[title_key(r)].append(r)
    new = set()
    for p in postings:
        old = by_uid.get(p["uid"]) or next((r for r in by_title[title_key(p)] if same_posting(r, p)), None)
        if old is None:
            old = dict(p, first_seen=date, last_seen=date)
            seen.append(old)
            by_title[title_key(p)].append(old)
            new.add(p["uid"])
        else:
            names = old["sources"].split("; ")
            for k in FIELDS:
                if p[k] and k not in ("uid", "sources"):
                    old[k] = p[k]
            old["sources"] = "; ".join(names + [s for s in p["sources"].split("; ") if s not in names])
            old["first_seen"], old["last_seen"] = min(old["first_seen"], date), max(old["last_seen"], date)
        by_uid.setdefault(p["uid"], old)
    return new


# --- watched pages -------------------------------------------------------------------

def watched_lines(path, w):
    """The lines of a saved page between `start` and `end` (config), and a note when a marker is missing."""
    lines = page_lines(path.read_text(encoding="utf-8", errors="replace"))
    if not w.get("start"):
        return lines, ""
    i = next((n for n, line in enumerate(lines) if w["start"] in line), None)
    if i is None:
        return lines, f"start text {w['start']!r} not found, so the whole page is compared"
    j = next((n for n in range(i + 1, len(lines)) if w.get("end") and w["end"] in lines[n]), len(lines))
    return lines[i:j], ""


def check_watched(cfg, date):
    """Compare each watched page fetched on `date` with its last copy. Returns (all changes, changes added now)."""
    WATCH.mkdir(parents=True, exist_ok=True)
    changes = read_csv(WATCH / "changes.csv")
    fetched = {r["source"]: r for r in read_csv(raw_dir(date) / "fetch.csv")}
    added_now = 0
    for w in cfg.get("watch", []):
        rec = fetched.get(f"watch:{w['id']}")
        if not rec or rec["status"] != "ok":
            say(f"watch {w['id']}: not fetched on {date} ({rec['status'] if rec else 'no request'}); not compared")
            continue
        lines, note = watched_lines(raw_dir(date) / rec["file"], w)
        store = WATCH / f"{w['id']}.txt"
        old = store.read_text(encoding="utf-8").splitlines() if store.exists() else None
        if old is None:
            say(f"watch {w['id']}: first copy kept, {len(lines)} lines {note}")
        elif old != lines:
            diff = list(difflib.ndiff(old, lines))
            added = [d[2:] for d in diff if d.startswith("+ ")]
            removed = [d for d in diff if d.startswith("- ")]
            changes.append(dict(date=date, id=w["id"], name=w["name"], url=w["url"],
                                added=" ¶ ".join(added)[:1500], removed=len(removed)))
            added_now += 1
            say(f"watch {w['id']}: changed, {len(added)} lines added, {len(removed)} removed {note}")
        else:
            say(f"watch {w['id']}: unchanged {note}")
        store.write_text("\n".join(lines), encoding="utf-8")
    write_csv(WATCH / "changes.csv", changes, CHANGE_FIELDS)
    return changes, added_now


# --- Markdown --------------------------------------------------------------------------

def esc(text):
    return re.sub(r"([\\`*_\[\]|<>])", r"\\\1", text or "")


def link(text, url):
    return f"[{esc(text)}]({(url or '').replace(' ', '%20').replace('(', '%28').replace(')', '%29')})"


class Page:
    """Writes postings as Markdown list items, grouped by profile."""

    def __init__(self, cfg, matches, date):
        self.cfg, self.matches, self.date = cfg, matches, date
        self.labels = {p["id"]: p["label"] for p in cfg["profiles"]}
        self.names = {s["id"]: s["name"] for s in cfg["sources"]}
        self.cap = cfg["settings"].get("max_per_profile", 40)
        self.new_since = days_before(date, cfg["settings"].get("new_days", 7))

    def item(self, row, mark_new=False):
        head = f"- {'🆕 ' if mark_new and row['first_seen'] >= self.new_since else ''}**{link(row['title'], row['url'])}**"
        if row["organisation"]:
            head += f" · {esc(row['organisation'])}"
        facts = [esc(row["location"]), esc(row["notes"]), f"posted {row['posted']}" if row["posted"] else "",
                 f"**deadline {row['deadline']}**" if row["deadline"] else ""]
        found = [self.names.get(s, s) for s in row["sources"].split("; ")]
        why = ""
        if self.matches.get(row["uid"]):
            score, _, terms = self.matches[row["uid"]][0]
            also = [self.labels[pid] for _, pid, _ in self.matches[row["uid"]][1:]]
            why = f"score {score}: {esc(', '.join(terms))}" + (f"; also fits *{'*, *'.join(also)}*" if also else "")
        lines = [head, " · ".join(f for f in facts if f), " · ".join(f for f in [why, "on " + ", ".join(found)] if f)]
        return "  \n  ".join(line for line in lines if line)

    def section(self, title, rows, intro="", mark_new=False):
        if not rows:
            return []
        out = [f"## {title} ({len(rows)})", ""] + ([intro, ""] if intro else [])
        out += [self.item(r, mark_new) for r in rows[:self.cap]]
        if len(rows) > self.cap:
            out.append(f"- and {len(rows) - self.cap} more with lower scores or later deadlines (all in data/seen.csv)")
        return out + [""]

    def by_profile(self, rows, sort_key, mark_new=False):
        out = []
        for p in self.cfg["profiles"]:
            mine = sorted((r for r in rows if self.matches[r["uid"]][0][1] == p["id"]), key=sort_key)
            out += self.section(p["label"], mine, f"*Fits:* {p['cv']}", mark_new)
        return out


def change_md(c):
    added = [a for a in c["added"].split(" ¶ ") if a][:6]
    out = [f"- **{link(c['name'], c['url'])}** changed on {c['date']}: {len(c['added'].split(' ¶ ')) if c['added'] else 0} lines new, {c['removed']} gone."]
    return out + [f"  > {esc(a)}" for a in added]


# --- main ------------------------------------------------------------------------------

def main():
    cfg, date = load_config(), run_date()
    postings = read_csv(ROOT / "data" / "postings" / f"{date}.csv")
    seen = read_csv(ROOT / "data" / "seen.csv")
    first_run = not seen
    new = update_seen(seen, postings, date)
    forget = days_before(date, cfg["settings"].get("forget_days", 365))
    seen = [r for r in seen if r["last_seen"] >= forget]
    write_csv(ROOT / "data" / "seen.csv", sorted(seen, key=lambda r: (r["first_seen"], r["uid"])), SEEN_FIELDS)
    say(f"{len(postings)} postings on {date}: {len(new)} new to data/seen.csv, which now holds {len(seen)}")

    scorer = Scorer(cfg)
    # platforms with score = false: listed in full, or only titles with a `keep` word if it has any
    unscored = {s["id"]: Terms(s.get("keep", [])) for s in cfg["sources"] if s.get("score") is False}
    first = lambda r: r["sources"].split("; ")[0]
    listed = [r for r in seen if first(r) in unscored and (not unscored[first(r)].rules or unscored[first(r)].found(r["title"]))]
    matches = {r["uid"]: m for r in seen if first(r) not in unscored and (m := scorer.score(r))}
    fits = [r for r in seen if r["uid"] in matches]
    changes, changed_now = check_watched(cfg, date)
    page = Page(cfg, matches, date)
    by_score = lambda r: -matches[r["uid"]][0][0]

    # digests/<date>.md: what appeared on this date
    today = [r for r in fits if r["first_seen"] == date]
    jobs, calls = [r for r in today if r["kind"] == "job"], [r for r in today if r["kind"] == "funding"]
    listed_today = [r for r in listed if r["first_seen"] == date]
    changed_today = [c for c in changes if c["date"] == date]
    md = [f"# Digest {date}", "",
          f"New on {date}: **{len(jobs)} postings** and **{len(calls)} funding calls** that fit a profile, "
          f"{len(listed_today)} items from {', '.join(page.names[s] for s in unscored)} (listed in full), "
          f"{len(changed_today)} watched pages changed. Everything still open: [open.md](../open.md). "
          f"What was asked and what came back: [log](../provenance/{date}.log.md).", ""]
    if first_run:
        md += ["*First run: everything the platforms list today counts as new.*", ""]
    md += page.by_profile(today, by_score)
    md += page.section("Listed in full (Greek-language feeds, not scored)", sorted(listed_today, key=lambda r: r["sources"]))
    if changed_today:
        md += [f"## Watched pages that changed ({len(changed_today)})", ""] + sum((change_md(c) for c in changed_today), []) + [""]
    (ROOT / "digests").mkdir(exist_ok=True)
    (ROOT / "digests" / f"{date}.md").write_text("\n".join(md), encoding="utf-8")

    # open.md: what can still be applied for
    keep = days_before(date, cfg["settings"].get("keep_days", 30))
    still_open = [r for r in fits if (r["deadline"] >= date) or (not r["deadline"] and r["last_seen"] >= keep)]
    soonest = lambda r: (r["deadline"] or "9999", -matches[r["uid"]][0][0])
    last = {c["id"]: c["date"] for c in changes}
    md = ["# Open now", "",
          f"Updated {date}. Postings with a deadline still ahead, or without one and seen in the last "
          f"{cfg['settings'].get('keep_days', 30)} days; soonest deadline first. 🆕 first seen in the last "
          f"{cfg['settings'].get('new_days', 7)} days. Daily lists: [index](index.md).", ""]
    md += page.by_profile(still_open, soonest, mark_new=True)
    md += page.section("Listed in full (Greek-language feeds, not scored)",
                       sorted((r for r in listed if r["last_seen"] >= keep), key=lambda r: r["first_seen"], reverse=True),
                       mark_new=True)
    md += ["## Watched pages", "", "| Page | Last changed |", "|---|---|"]
    md += [f"| {link(w['name'], w['url'])} | {last.get(w['id'], 'not since watching began')} |" for w in cfg.get("watch", [])]
    (ROOT / "open.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # index.md and data/runs.csv
    runs = [r for r in read_csv(ROOT / "data" / "runs.csv") if r["date"] != date]
    runs.append(dict(date=date, postings=len(jobs), calls=len(calls), listed=len(listed_today), changed=len(changed_today)))
    runs.sort(key=lambda r: r["date"], reverse=True)
    write_csv(ROOT / "data" / "runs.csv", runs, RUN_FIELDS)
    md = ["# Job postings and funding calls", "",
          f"Alerts for the {len(cfg['profiles'])} profiles in [config/profiles.toml](config/profiles.toml), built by scripts "
          f"from {sum(src.get('enabled', True) for src in cfg['sources'])} platforms and {len(cfg.get('watch', []))} watched pages. **[Open now](open.md)** has "
          "everything that can still be applied for; how it works is in [README.md](README.md).", "",
          "| Date | Postings | Funding calls | Listed in full | Pages changed | Digest | Log | Notes |", "|---|---|---|---|---|---|---|---|"]
    for r in runs:
        notes = ROOT / "notes" / f"{r['date']}.md"
        md.append(f"| {r['date']} | {r['postings']} | {r['calls']} | {r['listed']} | {r['changed']} | "
                  f"[digest](digests/{r['date']}.md) | [log](provenance/{r['date']}.log.md) | "
                  f"{f'[notes](notes/{notes.name})' if notes.exists() else ''} |")
    (ROOT / "index.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    new_fits = [r for r in fits if r["uid"] in new]
    new_listed = [r for r in listed if r["uid"] in new]
    say(f"{len(fits)} postings fit a profile, {len(still_open)} still open; on {date}: {len(jobs)} postings, "
        f"{len(calls)} calls, {len(listed_today)} listed in full, {len(changed_today)} pages changed")
    say(f"wrote digests/{date}.md, open.md, index.md, data/runs.csv")

    counts = [(sum(r["kind"] == "job" for r in new_fits), "posting", "postings"),
              (sum(r["kind"] == "funding" for r in new_fits), "funding call", "funding calls"),
              (len(new_listed), "item from HCMR/HFRI", "items from HCMR/HFRI"),
              (changed_now, "watched page changed", "watched pages changed")]
    message = ", ".join(f"{n} {one if n == 1 else many}" for n, one, many in counts if n)
    if message and cfg["settings"].get("notify", True) and not flag("no-notify"):
        shown = notify(f"Job postings: new on {date}", f"{message}. See http://127.0.0.1:8000")
        say(f"notified: {message}" if shown else f"new: {message} (no notification: no notifier, or it failed)")


def notify(title, message):
    """A desktop notification: osascript on a Mac, notify-send on Linux (package libnotify-bin)."""
    if sys.platform == "darwin":
        command = ["osascript", "-e", f'display notification "{message}" with title "{title}"']
    elif shutil.which("notify-send"):
        command = ["notify-send", title, message]
    else:
        return False
    return subprocess.run(command, check=False, capture_output=True).returncode == 0


if __name__ == "__main__":
    main()
