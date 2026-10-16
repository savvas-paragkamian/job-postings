"""How each platform is asked, and how its answer is read.

For every `type` in config/profiles.toml there are two functions:
  request_<type>(source, query, page)  -> (url, data, headers)  one HTTP request
  parse_<type>(body, source, date)     -> [posting, ...]        dicts with common.FIELDS
fetch.py sends the requests and saves the answers; parse.py reads them back with
the same parse functions. Nothing here touches the disk or the network.
"""
import datetime as dt
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET

from common import FIELDS, clean, iso_date, strip_tracking

EXTENSION = {"rss": "xml", "euraxess": "html", "workday": "json", "jrc": "json", "eu_funding": "json"}


def posting(**fields):
    row = dict.fromkeys(FIELDS, "")
    row.update({k: str(v or "") for k, v in fields.items()})
    return row


def fill(template, query, page):
    return template.format(query=urllib.parse.quote(query), page=page, page0=page - 1)


# --- RSS: Nature Careers, Science Careers, THE (search feeds); HCMR, HFRI (whole feeds) --

def request_rss(source, query, page):
    return fill(source["url"], query, page), None, {}


def parse_rss(body, source, date):
    out = []
    for item in ET.fromstring(body).iter("item"):
        title, org = clean(item.findtext("title")), source.get("organisation", "")
        lines = [line.strip() for line in (item.findtext("description") or "").splitlines() if line.strip()]
        notes = ""
        location = ""
        if source.get("title_has_employer"):
            # Madgex boards: title "Employer: Job title";
            # description "Salary:", "Employer:", text lines, and the place as the last line
            if ": " in title:
                org, title = title.split(": ", 1)
            if len(lines) >= 2 and lines[0].endswith(":") and lines[1].endswith(":"):
                notes, lines = lines[0][:-1], lines[2:]
            if len(lines) >= 2:
                location, lines = lines[-1], lines[:-1]
        url = strip_tracking(item.findtext("link"))
        out.append(posting(uid=url, title=title, organisation=org, location=location, notes=notes, url=url,
                           posted=iso_date(item.findtext("pubDate")), summary=clean(" ".join(lines))))
    return out


# --- EURAXESS: the EU's research jobs and funding portal (HTML search pages) ---------

request_euraxess = request_rss


def parse_euraxess(body, source, date):
    """One <article class="ecl-content-item"> per offer. The labelled fields (Work Locations,
    Researcher Profile, Application Deadline ...) are read from the article's plain text."""
    out = []
    for art in body.decode("utf-8", "replace").split('<article class="ecl-content-item">')[1:]:
        link = re.search(r'ecl-content-block__title">\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>', art, re.S)
        if not link:
            continue
        meta = [clean(m) for m in re.findall(r'primary-meta-item">(.*?)</li>', art, re.S)]
        desc = re.search(r'ecl-content-block__description">(.*?)</div>', art, re.S)
        text = clean(art)
        country = re.search(r"Number of offers: \d+, ([^,]+)", text)
        deadline = re.search(r"Deadline:\s*(\d{1,2} \w+ \d{4})", text)
        field = re.search(r"Research Field:\s*(.*?)\s*(?:Researcher Profile:|Funding Programme:|Application Deadline:|Deadline:|\{|$)", text)
        stages = sorted(set(re.findall(r"\((R[1-4])\)", text)))
        url = urllib.parse.urljoin("https://euraxess.ec.europa.eu", link[1])
        out.append(posting(
            uid=url, title=clean(link[2]), url=url,
            organisation=next((m for m in meta if not m.startswith("Posted on")), ""),
            posted=iso_date(next((m for m in meta if m.startswith("Posted on")), "")),
            location=country[1].strip() if country else "", notes=", ".join(stages),
            deadline=iso_date(deadline[1]) if deadline else "",
            summary=clean((field[1] + ". " if field else "") + (desc[1] if desc else ""))))
    return out


# --- Workday: EMBL and EMBL-EBI (JSON behind their careers site) ---------------------

def request_workday(source, query, page):
    body = {"appliedFacets": {}, "limit": 20, "offset": 20 * (page - 1), "searchText": query}
    return source["url"], json.dumps(body).encode(), {"Content-Type": "application/json", "Accept": "application/json"}


def parse_workday(body, source, date):
    out = []
    for job in json.loads(body).get("jobPostings", []):
        path = job.get("externalPath", "")
        # "Posted Today", "Posted Yesterday", "Posted 3 Days Ago", "Posted 30+ Days Ago"
        ago = job.get("postedOn", "")
        days = 0 if "Today" in ago else 1 if "Yesterday" in ago else int((re.findall(r"\d+", ago) or [0])[0])
        posted = (dt.date.fromisoformat(date) - dt.timedelta(days=days)).isoformat()
        out.append(posting(uid=f"{source['id']}:{(job.get('bulletFields') or [path])[0]}", title=job.get("title"),
                           organisation=source.get("organisation", ""), location=job.get("locationsText"),
                           posted=posted, url=source["link_base"] + path))
    return out


# --- JRC: the European Commission's Joint Research Centre (its portal's JSON) ----------

JRC_SITES = {1: "Seville", 2: "Geel", 3: "Petten", 4: "Brussels", 5: "Ispra", 6: "Karlsruhe"}  # api/common/allSites


def ms_date(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat() if ms else ""


request_jrc = request_rss


def parse_jrc(body, source, date):
    out = []
    for v in json.loads(body).get("content", []):
        title = re.sub(r"^\s*FG\s?I{1,3}V?\b\s*-?\s*", "", v.get("title") or "")   # the grade (FG IV) is in the code
        out.append(posting(uid=f"jrc:{v['id']}", title=title, organisation="JRC, " + (v.get("organizationInstitute") or ""),
                           location=", ".join(JRC_SITES.get(i, str(i)) for i in v.get("siteIds") or []), notes=v.get("code"),
                           posted=ms_date(v.get("startDate")), deadline=ms_date(v.get("endDate")),
                           url=f"https://recruitment.jrc.ec.europa.eu/vacancy/{v['id']}", summary=clean(v.get("shortDescription"))))
    return out


# --- EU Funding & Tenders Portal (the portal's own search API, public key SEDIA) --------

def request_eu_funding(source, query, page):
    """Call topics (type 1) and open calls of EU-funded projects (type 8, 'cascade funding'),
    forthcoming (31094501) or open (31094502). The API reads its filters only from a
    multipart form; a urlencoded form is silently ignored."""
    fields = {"query": {"bool": {"must": [{"terms": {"type": ["1", "8"]}},
                                          {"terms": {"status": ["31094501", "31094502"]}}]}},
              "languages": ["en"]}
    boundary = "job-postings-form"
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n'
             f"Content-Type: application/json\r\n\r\n{json.dumps(value)}\r\n" for name, value in fields.items()]
    data = ("".join(parts) + f"--{boundary}--\r\n").encode()
    return fill(source["url"], query, page), data, {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def parse_eu_funding(body, source, date):
    out = []
    for r in json.loads(body).get("results", []):
        m = r.get("metadata", {})
        first = lambda key: (m.get(key) or [""])[0]
        deadlines = sorted(filter(None, (iso_date(d) for d in m.get("deadlineDate") or [])))
        upcoming = [d for d in deadlines if d >= date]
        if deadlines and not upcoming:
            continue        # every deadline has passed: old project calls stay "open" in the index
        cascade = first("type") == "8"
        title, call = first("title") or r.get("summary", ""), first("callTitle")
        if cascade and call:
            title, call = f"{call}: {title}", ""
        status = {"31094501": "forthcoming", "31094502": "open"}.get(first("status"), "")
        opens = iso_date(first("startDate"))
        notes = ", ".join(filter(None, [status, "call of an EU-funded project" if cascade else "",
                                        f"opens {opens}" if opens > date else ""]))
        out.append(posting(uid="eu:" + str(r.get("reference") or first("identifier")), title=title,
                           organisation=first("identifier"), notes=notes, posted=opens if opens <= date else "",
                           deadline=upcoming[0] if upcoming else "", url=r.get("url"),
                           summary=clean(". ".join(filter(None, [call, first("description")])))))
    return out
