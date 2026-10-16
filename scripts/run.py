"""One run end to end: fetch, parse and write, then the provenance log.

    python3 scripts/run.py [YYYY-MM-DD] [--no-fetch] [--no-notify] [--once-a-day]
      --no-fetch    reuse the answers saved earlier that day (to try new keywords)
      --no-notify   no desktop notification
      --once-a-day  do nothing if a fetch that day already reached the platforms: cron calls
                    this every hour, so a computer that was off at 08:00 catches up later

Each step runs as its own process, so that what it prints goes into
provenance/<date>.log.md as printed. A successful run then deletes saved answers older
than settings.raw_days. This is the command cron (or launchd) runs every morning.
"""
import platform
import shutil
import subprocess
import sys
import time
from collections import defaultdict

from common import CONFIG, ROOT, VERSION, days_before, flag, load_config, md5, raw_dir, read_csv, run_date, say


def step(script, date, *extra):
    t0 = time.time()
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / script), date, *extra],
                       capture_output=True, text=True, cwd=ROOT)
    return dict(script=script, output=(p.stdout + p.stderr).rstrip(), status=p.returncode, seconds=round(time.time() - t0, 1))


def fetched_on(date):
    """True if a fetch on `date` got at least one answer (a fetch with the network down does not count)."""
    return any(r["status"] == "ok" for r in read_csv(raw_dir(date) / "fetch.csv"))


def main():
    date, t_start = run_date(), time.time()
    if flag("once-a-day") and fetched_on(date):
        return say(f"{date}: already fetched today, nothing to do (--once-a-day)")
    no_fetch = bool(flag("no-fetch"))
    steps = [] if no_fetch else [step("fetch.py", date)]
    if not steps or steps[-1]["status"] == 0:
        steps.append(step("parse.py", date))
    if steps[-1]["status"] == 0:
        steps.append(step("write.py", date, *(["--no-notify"] if flag("no-notify") else [])))
    for s in steps:
        say(f"--- {s['script']} ({s['seconds']} s, exit {s['status']})\n{s['output']}")

    fetched = read_csv(raw_dir(date) / "fetch.csv")
    per_source = defaultdict(int)
    for r in fetched:
        per_source[r["source"]] += int(r["items"] or 0)
    log = [f"# Run {date}, {time.strftime('%Y-%m-%d %H:%M:%S %Z')}", "",
           f"- Host {platform.node()}; Python {platform.python_version()}; job-postings {VERSION}",
           f"- Config: config/profiles.toml md5 {md5(CONFIG)}",
           f"- Mode: {'no fetch this run: answers saved by an earlier fetch that day, rescored' if no_fetch else 'live'}", "",
           "## Fetch", "",
           "| Platform | Query | Page | Status | Items | Seconds |", "|---|---|---|---|---|---|"]
    log += [f"| {r['source']} | {r['query']} | {r['page']} | {r['status']} | {r['items']} | {r['seconds']} |" for r in fetched]
    empty = [s for s, n in per_source.items() if n == 0 and not s.startswith("watch:")]
    failed = [r for r in fetched if r["status"] != "ok"]
    log += ["", "URLs as requested:", ""] + [f"- <{r['url']}>" for r in fetched] + [""]
    for s in steps:
        log += [f"## {s['script']} ({s['seconds']} s, exit {s['status']})", ""] + [f"    {line}" for line in s["output"].splitlines()] + [""]
    log += ["## Failures and warnings", ""]
    log += [f"- {r['source']} `{r['query']}` page {r['page']}: {r['status']}" for r in failed]
    log += [f"- {s}: no postings from any query; if this repeats, the site may have changed" for s in empty]
    log += [] if failed or empty else ["- none"]
    log += ["", f"Wall time: {time.time() - t_start:.1f} s."]
    (ROOT / "provenance").mkdir(exist_ok=True)
    (ROOT / "provenance" / f"{date}.log.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    say(f"\nwrote provenance/{date}.log.md")
    if any(s["status"] != 0 for s in steps):
        say("a step failed; see above")
        sys.exit(1)
    prune(date)


def prune(date):
    """Delete saved answers and day tables older than settings.raw_days: data/seen.csv,
    the digests and the logs are the lasting record; these only serve to rescore a day."""
    oldest = days_before(date, load_config()["settings"].get("raw_days", 14))
    gone = [p for p in (ROOT / "data" / "raw").glob("*") if p.is_dir() and p.name < oldest]
    gone += [p for p in (ROOT / "data" / "postings").glob("*.csv") if p.stem < oldest]
    for p in gone:
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    if gone:
        say(f"deleted {len(gone)} saved days older than {oldest}")


if __name__ == "__main__":
    main()
