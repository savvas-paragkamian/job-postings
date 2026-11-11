"""Shared helpers for the job-postings scripts: paths, config, dates, HTTP,
text cleaning, keyword matching, scoring and CSV files.

Standard library only; Python 3.11 or newer (tomllib reads the config).
Run the scripts from anywhere: paths are relative to this repository.
"""
import csv
import datetime as dt
import email.utils
import gzip
import hashlib
import html
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit(f"Python 3.11 or newer is needed (for tomllib); this is {sys.version.split()[0]}")
import tomllib

VERSION = "0.1"
ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "profiles.toml"

# One row per posting in data/postings/<date>.csv; data/seen.csv adds the dates.
FIELDS = ["uid", "kind", "sources", "title", "organisation", "location", "notes",
          "posted", "deadline", "url", "summary"]
SEEN_FIELDS = FIELDS + ["first_seen", "last_seen"]
SUMMARY_CHARS = 1000


def say(*args):
    print(*args, flush=True)


# --- config, dates, arguments --------------------------------------------------

def load_config(path=CONFIG):
    with open(path, "rb") as f:
        return tomllib.load(f)


def run_date(argv=None):
    """The date a run is filed under: the first argument like 2026-10-16, else today."""
    args = [a for a in (sys.argv[1:] if argv is None else argv) if not a.startswith("--")]
    if not args:
        return dt.date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args[0]):
        sys.exit(f"the date must look like 2026-10-16, got: {args[0]}")
    return args[0]


def flag(name, argv=None):
    """--name gives True, --name=a,b gives ['a', 'b'], absent gives None."""
    for a in (sys.argv[1:] if argv is None else argv):
        if a == f"--{name}":
            return True
        if a.startswith(f"--{name}="):
            return a.split("=", 1)[1].split(",")
    return None


def raw_dir(date):
    return ROOT / "data" / "raw" / date


def days_before(date, n):
    return (dt.date.fromisoformat(date) - dt.timedelta(days=n)).isoformat()


def iso_date(text):
    """A date in any of the platforms' formats as YYYY-MM-DD, or '' if there is none.
    Handles 2026-12-02T17:00:00.000+0000, RSS dates (Wed, 14 Oct 2026 12:16:00 +0000),
    and 28 Oct 2026 - 18:00 or 1 December 2026 as EURAXESS writes them."""
    text = (text or "").strip()
    if not text:
        return ""
    m = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if m:
        return m.group(0)
    try:
        return email.utils.parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", text)
    if m:
        try:
            return dt.datetime.strptime(f"{m[1]} {m[2].title()} {m[3]}", "%d %b %Y").date().isoformat()
        except ValueError:
            pass
    return ""


# --- HTTP ----------------------------------------------------------------------

def user_agent(cfg):
    contact = cfg["settings"].get("contact", "")
    return f"Mozilla/5.0 (compatible; job-postings/{VERSION}; personal job alerts{'; mailto:' + contact if contact else ''})"


def http(url, cfg, data=None, headers=None, timeout=60, tries=3):
    """GET, or POST when data is given. Returns (status, body, error); status 0 when
    there was no answer. Network errors and HTTP 429/5xx are retried after 5 and 10 s."""
    hdrs = {"User-Agent": user_agent(cfg), **(headers or {})}
    status, body, err = 0, b"", ""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=hdrs), timeout=timeout) as r:
                body = r.read()
                if r.headers.get("Content-Encoding", "").lower() == "gzip":   # sent unasked (Academic Jobs Online)
                    body = gzip.decompress(body)
                return r.status, body, ""
        except urllib.error.HTTPError as e:
            status, body, err = e.code, e.read(), f"HTTP {e.code}"
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            status, body, err = 0, b"", f"no answer: {getattr(e, 'reason', e)}"
        if attempt < tries - 1:
            time.sleep(5 * (attempt + 1))
    return status, body, err


# --- text ----------------------------------------------------------------------

def clean(fragment, limit=None):
    """Plain text from an HTML fragment, whitespace collapsed, cut at a word near `limit`."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", fragment or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + " ..."
    return text


def page_lines(page):
    """The visible text of a web page, one line per paragraph, list item or heading."""
    page = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|template)\b.*?</\1>", " ", page)
    page = re.sub(r"(?i)<(br|/p|/div|/li|/h\d|/tr|/dt|/dd|/section|/article)\b[^>]*>", "\n", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    lines = (re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.splitlines())
    return [line for line in lines if len(line) > 2]


def strip_tracking(url):
    """The URL without utm_* and TrackID parameters, so that one posting has one address."""
    parts = urllib.parse.urlsplit((url or "").strip())
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if not k.lower().startswith(("utm_", "trackid"))]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def fold(text):
    """Lower case without accents: 'Écologie' becomes 'ecologie'."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def title_key(row):
    """The kind and the title in plain lower-case words: rows with one key may be one posting."""
    return row["kind"] + ": " + " ".join(re.sub(r"[^a-z0-9]+", " ", fold(row["title"])).split())


ORG_FILLER = {"university", "universite", "universita", "universitat", "universidad", "institute", "institut",
              "school", "college", "department", "centre", "center", "research", "national", "sciences", "science"}


def same_posting(a, b):
    """Two rows with different uids are one posting when two platforms list the same title.
    A title under six words ('Bioinformatician') must also come with organisations that share
    a name word ('UC Irvine, Charlie Dunlop School' and 'Charlie Dunlop School'). One platform
    lists a posting once, so two of its rows with one title are two postings: HCMR's calls
    all read 'Call for expressions of interest ...'."""
    if set(a["sources"].split("; ")) & set(b["sources"].split("; ")) or title_key(a) != title_key(b):
        return False
    words = lambda org: {w for w in re.sub(r"[^a-z0-9]+", " ", fold(org)).split() if len(w) > 3 and w not in ORG_FILLER}
    return len(title_key(a).split()) >= 7 or bool(words(a["organisation"]) & words(b["organisation"]))


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


# --- keywords and scores ---------------------------------------------------------

class Terms:
    """A list of keywords, matched by the rules written at the top of config/profiles.toml:
    whole words only; a trailing * matches any ending; capitals are case-sensitive;
    accents ignored; a space or hyphen in a keyword matches a space, a hyphen or nothing."""

    def __init__(self, terms):
        self.rules = []
        for term in terms:
            exact = term.upper() == term and any(c.isalpha() for c in term)
            stem = term[:-1] if term.endswith("*") else term
            body = re.sub(r"\\[ -]", r"[\\s-]?", re.escape(stem if exact else fold(stem)))
            rx = re.compile(r"(?<!\w)" + body + (r"\w*" if term.endswith("*") else r"(?!\w)"))
            self.rules.append((term, rx, exact))

    def found(self, text):
        """The keywords that occur in text, in the order of the config."""
        folded = fold(text)
        return [term for term, rx, exact in self.rules if rx.search(text if exact else folded)]


POSTDOC = Terms(["post-doc*"])   # postdoc, post-doc, postdoctoral: some employers mark postdocs R1 on EURAXESS


class Scorer:
    """Scores postings against the profiles of config/profiles.toml."""

    def __init__(self, cfg):
        s = cfg["settings"]
        self.weight = s.get("title_weight", 3)
        self.min_score = s.get("min_score", 3)
        self.skip_stages = set(s.get("skip_stages", []))
        self.profiles = cfg["profiles"]
        self.terms = {p["id"]: Terms(p["keywords"]) for p in self.profiles}
        self.require = {p["id"]: Terms(p["require"]) for p in self.profiles if p.get("require")}
        self.exclude = {kind: Terms(words) for kind, words in cfg.get("exclude", {}).items()}
        self.source_min = {src["id"]: src["min_score"] for src in cfg["sources"] if "min_score" in src}

    def score(self, row):
        """[(score, profile id, keywords found)] for each profile of the row's kind that the
        row reaches (and, if the profile has `require`, mentions one of those), best first.
        [] if an excluded word is in the title, or if a EURAXESS offer is open only to the
        researcher stages in settings.skip_stages."""
        excluded = self.exclude.get(row["kind"])
        if excluded and excluded.found(row["title"]):
            return []
        stages = set(re.findall(r"\bR[1-4]\b", row["notes"]))
        if stages and stages <= self.skip_stages and not POSTDOC.found(row["title"]):
            return []
        # a platform's own min_score (config) applies to the postings it found
        threshold = min(self.source_min.get(s, self.min_score) for s in row["sources"].split("; "))
        text = row["organisation"] + " . " + row["summary"]
        out = []
        for p in self.profiles:
            if p["kind"] != row["kind"]:
                continue
            if p["id"] in self.require and not self.require[p["id"]].found(row["title"] + " . " + text):
                continue
            in_title = self.terms[p["id"]].found(row["title"])
            in_text = [t for t in self.terms[p["id"]].found(text) if t not in in_title]
            score = self.weight * len(in_title) + len(in_text)
            if score >= max(threshold, 1):
                out.append((score, p["id"], in_title + in_text))
        return sorted(out, key=lambda x: -x[0])


# --- CSV -------------------------------------------------------------------------

def read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
