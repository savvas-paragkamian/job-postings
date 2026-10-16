# job-postings

Job and funding alerts that fit one CV. Every morning, scripts search ten platforms
for postings and calls, score each against five profiles drawn from the CV of
Savvas Paragkamian, keep what fits, and write Markdown pages. A small local web
server then shows those pages in the browser. A desktop notification (macOS or
Linux) says when something new has arrived.

It follows the layout of `weekly-literature`. A config file written by hand holds
the vocabulary. Numbered steps fetch, read and write, and the raw answers are kept
for a while. `seen.csv` remembers what was shown before, and each run leaves a
provenance log. A clock runs it, and an optional assistant skill writes labelled
notes that stay separate from the scripts' output.

Only the Python standard library is used (Python 3.11 or newer). There is nothing
to install.

## Quick start

```bash
cd ~/projects/job-postings
python3 scripts/run.py               # fetch, score and write today's pages (about 4 minutes)
python3 scripts/serve.py --open      # http://127.0.0.1:8000 in the browser; Ctrl-C stops it
python3 -m unittest discover tests   # the checks, no network
```

The page has three parts. **Open now** (`open.md`) lists everything that can still
be applied for, by profile, soonest deadline first. **Index** (`index.md`) has one
line per day, linking to that day's digest (`digests/<date>.md`, only what was new
that day) and its log. **Profiles & platforms** shows the config.

## The five profiles

Each profile is a way the CV reads to an employer or a funder. It has `queries`,
which are sent to the platforms that search, and `keywords`, which score every
posting. A `cv` line is printed above its list. All of it is in
[config/profiles.toml](config/profiles.toml).

| Profile | Rests on (CV) | Modelled on (examples/) |
|---|---|---|
| **Microbial ecology & computational (meta)genomics** | PhD on the soil microbiome interactome; Island Sampling Day Crete metagenomes; Gourgouthakas Cave 16S; endophyte genomes and BGC mining; EMBL TREC multi-omics | WUR postdoc on computational (meta)genomics and BGCs |
| **Biodiversity informatics, text mining & AI** | KYBELE (LLM extraction, ELIXIR); PREGO, DECO; EMODnet; Darwin Core, MIxS; Dawn Field Award | none among the PDFs: data posts at GBIF, EMBL-EBI, ELIXIR, LifeWatch, museums |
| **Soil health, biodiversity monitoring & science for policy** | NECCA Article 17 assessments; Natura 2000 status of Cretan endemics; Cave Fauna of Greece database; EUSO forum | JRC vacancy notice: soil nutrients, LUCAS soil monitoring |
| **Complex systems, networks & quantitative ecology** | MSc Complex Systems and Networks; interactome networks; Arena3Dweb; network science teaching | SFI Complexity Postdoctoral Fellowship (a yearly call, watched) |
| **Fellowships & funding calls** (proposal opportunities) | TETTRIX, KYBELE, CCMRI proposals; HFRI scholarship; EMBL CPP fellowship; PhD 2024, within the MSCA PF and ERC StG windows | MSCA, ERC, EMBO, HFSP, Humboldt, SFI; EU calls on soil, biodiversity, microbiomes |

On the first live runs (16 October 2026), 1,330 postings were read and 788 were
distinct. Of these, 134 fit a profile: 45, 3, 32, 5 and 49 in the order above, and
11 more came from the Greek feeds. The informatics and complex-systems lists are
short because few such posts are advertised, not because of the filter: the
near-misses were generic AI, finance and computer-networks posts (see AGENTS.md).

## Platforms

Each platform below was checked by hand on 16 October 2026 and answered a script
without a key or a login. `type` in the config names the code in
`scripts/sources.py` that talks to it.

| Platform | What it adds | How it is read | Kind |
|---|---|---|---|
| [EURAXESS](https://euraxess.ec.europa.eu/jobs/search) | the EU's research jobs portal; also carries AcademicTransfer (Dutch universities, WUR), THE and Academic Positions | search page per query, 2 pages, HTML read by `parse_euraxess` | jobs |
| [Nature Careers](https://www.nature.com/naturecareers) | academic and industry science posts worldwide | RSS search feed per query, 2 pages | jobs |
| [Science Careers](https://jobs.sciencecareers.org) | AAAS board, strong in North America | RSS search feed per query | jobs |
| [Times Higher Education jobs](https://www.timeshighereducation.com/unijobs/) | universities, UK and worldwide | RSS search feed per query | jobs |
| [EMBL and EMBL-EBI](https://www.embl.org/jobs/) | all six EMBL sites | the JSON behind their Workday site, every post, titles scored | jobs |
| [JRC](https://recruitment.jrc.ec.europa.eu/) | the Commission's Joint Research Centre (EU Soil Observatory, Land and Climate) | the portal's JSON, every vacancy; one keyword is enough | jobs |
| [HCMR calls](https://calls.hcmr.gr/category/job-opportunities/) | the home institute, in Greek | RSS, listed in full (calls and hirings only) | jobs |
| [EU Funding & Tenders](https://ec.europa.eu/info/funding-tenders/opportunities/portal/) | Horizon Europe (MSCA, ERC, Missions, Cluster 6), LIFE, and open calls of EU projects | the portal's search API, open and forthcoming only | funding |
| [EURAXESS funding](https://euraxess.ec.europa.eu/funding/search) | fellowships and grants worldwide | search page per query | funding |
| [HFRI (ELIDEK)](https://www.elidek.gr/) | the Greek national funder | RSS, listed in full (calls and posts only) | funding |

Six pages without a feed are **watched**: the SFI Complexity Postdoctoral
Fellowship, ERC Starting Grant, MSCA Postdoctoral Fellowships, EMBO Postdoctoral
Fellowships, HFSP Fellowships and the Humboldt Research Fellowship. Each run keeps
the part of the page between two marker lines. When it changes, the digest quotes
the new lines (for example SFI's "Opens Jul 26 2027 …").

**Tried and left out.**
- LinkedIn, Indeed and Glassdoor have no public API and forbid scraping.
- ELIXIR's and GBIF's job pages answer scripts with 403 (Cloudflare).
- No working feed was found for jobs.ac.uk; its posts reach Nature and THE.
- AcademicTransfer and Academic Positions arrive through EURAXESS.
- New Scientist Jobs has closed.
- ecoevojobs.net is a US spreadsheet, and Research Professional needs a subscription.
- HFRI's calls page is drawn in the browser, so its feed is used instead.

**Two details that took finding out.** EURAXESS has no RSS: its search form posts
and redirects to `?f[0]=keywords:<query>`, the address the config uses. The EU
portal's API reads its filters only from a multipart form; a URL-encoded form is
silently ignored and returns all 32,000 records.

## How a posting is chosen

1. **Score.** For each profile, a keyword in the title counts 3, and a keyword in
   the employer or summary counts 1. A posting is listed under its best profile
   once it reaches 3, which means one keyword in the title or three in the text.
   The other profiles it reaches are named next to it.
2. **Keyword rules.** Whole words only (`cave` is not `caveat`). A trailing `*`
   matches any ending (`metagenom*`). Capitals are case-sensitive (`MAG` is not
   `magnetic`, `FAIR` is not "a fair salary"). Accents are ignored, and Greek works.
3. **`require`.** Three profiles count a posting only if it also mentions their
   subject: an AI post must touch biology or the environment, and a funding call
   must touch life on Earth or be a fellowship.
4. **Left out.** Titles with an excluded word are dropped: PhD posts, master's,
   internships, medicine, finance. So are EURAXESS offers open only to R1
   (first-stage) researchers, unless the title says postdoc.
5. **Duplicates.** The same posting found by two queries is shown once, and so is
   the same title on two platforms. One platform's identical titles stay separate
   (HCMR's calls all read alike).
6. **Funding calls.** EU calls whose deadlines have all passed are dropped. The EU
   index keeps some old project calls marked "open".

To see why something was or wasn't listed, look at the score line under it ("score
6: metagenom*, microbial"). The log has every query and how many answers it
brought.

## Changing what it looks for

Edit `config/profiles.toml`, then rescore today's saved answers without asking
the platforms again:

```bash
python3 scripts/run.py --no-fetch
```

You can add a query or keyword, add a watched page (`[[watch]]` with `url`,
`start`, `end`), or add a platform. A platform with an RSS feed only needs a
`[[sources]]` block of `type = "rss"`; a new kind of platform needs a
`request_<type>` and a `parse_<type>` in `scripts/sources.py`, plus a saved answer
and a test in `tests/`.

## Files

| Path | Contents |
|---|---|
| `config/profiles.toml` | settings, exclusions, the five profiles, ten platforms, six watched pages |
| `scripts/common.py` | shared helpers: dates, HTTP, text, keyword rules (`Terms`), scoring (`Scorer`), CSV |
| `scripts/sources.py` | one `request_` and one `parse_` function per kind of platform |
| `scripts/fetch.py` | step 1: ask every platform, save each answer in `data/raw/<date>/`, with `fetch.csv` |
| `scripts/parse.py` | step 2: read the answers into `data/postings/<date>.csv`, one row per posting |
| `scripts/write.py` | step 3: score, update `data/seen.csv`, compare watched pages, write the pages, notify |
| `scripts/run.py` | steps 1 to 3 and `provenance/<date>.log.md`; deletes saved answers older than 14 days; `--once-a-day` for cron |
| `scripts/serve.py` | the local web page, with its own small Markdown converter |
| `index.md`, `open.md`, `digests/<date>.md` | the pages (script output) |
| `data/seen.csv` | every posting ever fetched, with first and last date seen; the lasting record |
| `data/watch/` | the watched texts as last seen, and `changes.csv` |
| `provenance/<date>.log.md` | every request of a run: query, status, items, seconds, URL; failures |
| `tests/` | checks and the trimmed real answers they run on |
| `cron/`, `launchd/` | the daily clock: cron (Linux and macOS) or launchd (macOS) |
| `.claude/skills/job-fit/` | the optional assistant (below) |
| `examples/` | the CV and the postings the profiles were modelled on |

## Every morning

**cron (Linux and macOS).** `cron/job-postings.crontab` calls
`scripts/run.py --once-a-day` every hour from 08:00 to 20:00. The first run of the
day that reaches the platforms does the work; the later ones see that and stop at
once. So a computer that was off or asleep at 08:00 catches up within an hour of
starting. Edit the Python path in the file first. It needs 3.11 or newer:
`/usr/bin/python3` on Ubuntu 24.04 or Debian 12, `/Users/talos/miniconda3/bin/python3`
on this Mac (macOS's own 3.9 is too old). Then:

```bash
(crontab -l 2>/dev/null; cat cron/job-postings.crontab) | crontab -    # adds the line, keeps the rest
crontab -l                                                             # check
```

What the runs print goes to `provenance/cron.log`.

**launchd (macOS only), the alternative.** `launchd/org.paragkamian.job-postings.plist`
runs `scripts/run.py` at 08:30, and on waking if the Mac was asleep. It runs inside
the login session, so its notifications always show; macOS may not show those of
a cron job. Use one clock, not both:

```bash
cp launchd/org.paragkamian.job-postings.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/org.paragkamian.job-postings.plist
launchctl kickstart -k gui/$(id -u)/org.paragkamian.job-postings    # once now, to try it
```

**Notifications.** When a run finds something new, a desktop notification says so,
for example "6 postings, 2 funding calls, 1 watched page changed". It uses
`osascript` on macOS and `notify-send` on Linux (package `libnotify-bin`). From
cron, Linux needs the desktop session's message bus: uncomment the
`DBUS_SESSION_BUS_ADDRESS` line in the crontab file. Without a notifier the run
still writes its pages and says "no notification" in the log. Then
`python3 scripts/serve.py --open` shows what is new. Set `notify = false` in the
config to silence it.

## Optional: assistant notes

`/job-fit <date>` in Claude Code reads that day's digest, the CV and each chosen
posting's own page. It writes `notes/<date>.md`: requirements quoted from the
posting, what the CV meets and what it doesn't, and the deadline. The file is
labelled as written by an AI assistant, and the index links to it. Nothing in
`scripts/` depends on it, and it may write only in `notes/`.

## Limits

- Searches return what each platform ranks first: two pages a query on EURAXESS and
  Nature, one elsewhere. A daily run catches new posts, but a quiet query can miss
  an old one.
- EMBL and JRC lists give titles only; the JRC also gives its unit's name. A
  vaguely titled post ("Project Officer") is scored on little text.
- RSS boards give a short summary and no deadline. The deadline is on the posting.
- HTML pages change. When a platform returns nothing at all, the log's warnings
  say so. Save a fresh answer in `tests/fixtures/` and the tests show which reader broke.
- Scores are keyword counts, not judgement. The profiles, `require` and the
  exclusions are the method, so tune them from what the pages show.
