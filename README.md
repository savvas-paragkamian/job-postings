# job-postings

Job and funding alerts that fit one CV. Every morning, scripts search fourteen platforms
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
without a key or a login. On 11 November 2026 each was checked again against its
robots.txt, and the postdoc boards were added (below). `type` in the config names
the code in `scripts/sources.py` that talks to it.

| Platform | What it adds | How it is read | Kind |
|---|---|---|---|
| [Nature Careers](https://www.nature.com/naturecareers/jobs/postdoctoral/) | academic and industry science posts worldwide | category pages, in full: every postdoc post, and research posts in life and environmental science (about 23 pages), HTML read by `parse_madgex` | jobs |
| [Science Careers](https://jobs.sciencecareers.org) | AAAS board, strong in North America | RSS search feed per query | jobs |
| [Times Higher Education jobs](https://www.timeshighereducation.com/unijobs/listings/research-related/) | universities, UK and worldwide | category page "research-related" in full: postdoc, fellow and research associate posts in every subject (about 6 pages) | jobs |
| [jobs.ac.uk](https://www.jobs.ac.uk) | UK and European universities, with salary and closing date | search page per query (25 results), HTML read by `parse_jobs_ac_uk` | jobs |
| [jobRxiv](https://jobrxiv.org) | non-profit science board, many postdocs; employer and country | the board's search as RSS, per query (50 results) | jobs |
| [FEMS jobs](https://fems-microbiology.org/opportunities/) | microbiology only, mostly PhD and postdoc posts | RSS, the latest 10 | jobs |
| [Max Planck Society](https://www.mpg.de/jobboard) | every Max Planck institute | RSS, the latest 30 | jobs |
| [Berkeley Lab](https://lbl.referrals.selectminds.com/page/jgi-job-openings-68) | the DOE Joint Genome Institute's openings (metagenomics, microbial genomics), and every Berkeley Lab postdoc post | two landing pages (JGI openings, postdoctoral fellows), the newest 10 of each, HTML read by `parse_selectminds` | jobs |
| [Academic Jobs Online](https://academicjobsonline.org/ajo/jobs) | about 360 adverts with deadlines; mostly physics and mathematics, but also US postdocs in microbiome and plant-microbe science | one RSS 1.0 feed (2 MB), every advert scored | jobs |
| [EMBL and EMBL-EBI](https://www.embl.org/jobs/) | all six EMBL sites | the JSON behind their Workday site, every post, titles scored | jobs |
| [JRC](https://recruitment.jrc.ec.europa.eu/) | the Commission's Joint Research Centre (EU Soil Observatory, Land and Climate) | the portal's JSON, every vacancy; one keyword is enough | jobs |
| [HCMR calls](https://calls.hcmr.gr/category/job-opportunities/) | the home institute, in Greek | RSS, listed in full (calls and hirings only) | jobs |
| [EU Funding & Tenders](https://ec.europa.eu/info/funding-tenders/opportunities/portal/) | Horizon Europe (MSCA, ERC, Missions, Cluster 6), LIFE, and open calls of EU projects | the portal's search API, open and forthcoming only | funding |
| [HFRI (ELIDEK)](https://www.elidek.gr/) | the Greek national funder | RSS, listed in full (calls and posts only) | funding |
| [EURAXESS](https://euraxess.ec.europa.eu/jobs) jobs and funding | the EU's research portal: jobs, and fellowships and grants worldwide; carried AcademicTransfer, Academic Positions and many Italian and French posts | **off** since 11 November 2026 (below); search page per query, read by `parse_euraxess` | jobs, funding |

**Where the new boards came from.** jobs.ac.uk, jobRxiv, FEMS and Max Planck are
among the boards read every day by [Microbiome Faculty Jobs](https://callaband.github.io/microbiome-faculty-jobs/),
a list of faculty posts in microbiome science; its collector
([config/sources.yaml](https://github.com/callaband/microbiome-faculty-jobs/blob/main/config/sources.yaml))
obeys robots.txt, and showed which route each board allows. Academic Jobs Online
is on its "where else to look" list. Here they are read for postdocs: by search
where the board has one, and scored with the same five profiles. Berkeley Lab was
added on 13 November 2026 at the author's request: its JGI openings page, and the
lab's postdoctoral page beside it; robots.txt allows both.

**robots.txt.** Nature's and THE's robots.txt disallow their keyword RSS
(`/naturecareers/jobsrss/`, `/unijobs/jobsrss/`), which this project read until
11 November 2026, but not their category pages. For a postdoc search these are the
better route anyway: every postdoc post on the board is read and scored, not only
what a keyword search ranks first. EURAXESS changed its robots.txt on 10 November
2026 to disallow `/jobs/*` and every URL with parameters: its job search, its
funding search and the job pages. There is no allowed route, so both EURAXESS
sources have `enabled = false`. Ask support@euraxess.org for permission or an export
of the job offers, and switch them on again only with their agreement. Until then
the postings found only there are missing: 62 of the 267 that had fitted by
11 November, 36 of them still open, mostly in Italy and France.

Six pages without a feed are **watched**: the SFI Complexity Postdoctoral
Fellowship, ERC Starting Grant, MSCA Postdoctoral Fellowships, EMBO Postdoctoral
Fellowships, HFSP Fellowships and the Humboldt Research Fellowship. Each run keeps
the part of the page between two marker lines. When it changes, the digest quotes
the new lines (for example SFI's "Opens Jul 26 2027 …").

**Tried and left out.**
- LinkedIn, Indeed and Glassdoor have no public API and forbid scraping.
- ELIXIR's and GBIF's job pages answer scripts with 403 (Cloudflare).
- AcademicTransfer (Dutch universities, where the WUR example was posted): its
  search is drawn in the browser, and robots.txt closes its API host to scripts.
- Academic Positions refused the Microbiome Faculty Jobs collector (403), and
  Academics.com's terms forbid automated reading; both reached this project through
  EURAXESS while it was on.
- Helmholtz disallows every URL with parameters; University Positions disallows its
  RSS, and its postdoc page held 8 posts; no machine-readable search was found for
  Jobbnorge.
- New Scientist Jobs has closed.
- ecoevojobs.net is a US spreadsheet, and Research Professional needs a subscription.
- HFRI's calls page is drawn in the browser, so its feed is used instead.

**Details that took finding out.** EURAXESS has no RSS: its search form posts
and redirects to `?f[0]=keywords:<query>`, the address the config keeps for when
it is on. The EU portal's API reads its filters only from a multipart form; a
URL-encoded form is silently ignored and returns all 32,000 records. Madgex boards
(Nature, THE) number their category pages in the path (`/postdoctoral/2/`), and a
page past the last repeats the last one, which ends the paging. jobs.ac.uk writes
its dates without a year ("Closes 23 Nov"). Academic Jobs Online sends gzip even
when not asked, and `common.http` unpacks it. Berkeley Lab's board (SelectMinds)
puts the newest 10 jobs of a landing page in the HTML and loads the rest by
script, so one page a day is read; it dates a job "1 day ago" or "Nov 05, 2026".

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
and a test in `tests/`. Check the platform's robots.txt first. `enabled = false`
switches a platform off; `queries` in a platform's block replaces the profiles'
queries (on Nature and THE they are category paths).

## Files

| Path | Contents |
|---|---|
| `config/profiles.toml` | settings, exclusions, the five profiles, sixteen platforms (two off), six watched pages |
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

- Searches return what each platform ranks first: one page a query (20 on Science,
  25 on jobs.ac.uk, 50 on jobRxiv). A daily run catches new posts, but a quiet query
  can miss an old one. Nature and THE are read in full, by category instead.
- EMBL and JRC lists give titles only; the JRC also gives its unit's name. A
  vaguely titled post ("Project Officer") is scored on little text. Nature and THE
  category pages give the first two lines of the advert, Berkeley Lab's about 150
  characters: its three "Postdoctoral Researcher" posts in ecology and soil science
  reached 1 or 2 on 13 November.
- Most boards give no deadline (Academic Jobs Online and jobs.ac.uk do). The
  deadline is on the posting.
- Long adverts (Academic Jobs Online, jobRxiv) reach the score of 3 more easily
  through general words in the text ("policy", "monitoring", "data scientist").
- HTML pages change. When a platform returns nothing at all, the log's warnings
  say so. Save a fresh answer in `tests/fixtures/` and the tests show which reader broke.
- Scores are keyword counts, not judgement. The profiles, `require` and the
  exclusions are the method, so tune them from what the pages show.
