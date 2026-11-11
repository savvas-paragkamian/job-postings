"""Checks that can fail, without the network:

    python3 -m unittest discover tests      (or: python3 tests/test_scripts.py)

- the keyword rules of config/profiles.toml (whole words, *, capitals, accents, Greek);
- each platform's reader on a trimmed copy of a real answer (tests/fixtures/, 16 October and
  11 November 2026): if a site changes its pages, save a new answer here and this is where it shows;
- scoring with the real config: planted postings that must, and must not, be listed;
- merging, dates, the watched-page markers, and the local web page (its Markdown,
  and a real server on a free port: pages, the tab icon, a missing page).
"""
import gzip
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sources  # noqa: E402
from common import FIELDS, Scorer, Terms, http, iso_date, load_config, same_posting  # noqa: E402
from fetch import queries_for  # noqa: E402
from serve import Handler, markdown  # noqa: E402
from write import watched_lines  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CFG = load_config()
SOURCE = {s["id"]: s for s in CFG["sources"]}
DATE = "2026-10-16"
DATE2 = "2026-11-11"     # the answers saved for the platforms added on 11 November 2026


def row(**fields):
    r = dict.fromkeys(FIELDS, "")
    r.update(kind="job", sources="euraxess")
    r.update(fields)
    return r


class KeywordRules(unittest.TestCase):
    def test_whole_words(self):
        self.assertEqual(Terms(["cave"]).found("a caveat about caves"), [])
        self.assertEqual(Terms(["cave"]).found("Gourgouthakas cave, Crete"), ["cave"])

    def test_trailing_star(self):
        self.assertEqual(Terms(["metagenom*"]).found("Computational Metagenomics"), ["metagenom*"])

    def test_capitals_are_case_sensitive(self):
        self.assertEqual(Terms(["MAG", "FAIR"]).found("magnetic fields, a fair salary"), [])
        self.assertEqual(Terms(["MAG", "FAIR"]).found("MAG binning and FAIR data"), ["MAG", "FAIR"])

    def test_accents_and_hyphens(self):
        self.assertEqual(Terms(["ecolog*"]).found("Écologie microbienne"), ["ecolog*"])
        self.assertEqual(Terms(["multi-omic*"]).found("multiomics and multi omics"), ["multi-omic*"])

    def test_greek(self):
        self.assertEqual(Terms(["προσκληση*"]).found("ΠΡΟΣΚΛΗΣΗ ΕΚΔΗΛΩΣΗΣ ΕΝΔΙΑΦΕΡΟΝΤΟΣ"), ["προσκληση*"])
        self.assertEqual(Terms(["προσκληση*"]).found("ΠΡΑΚΤΙΚΟ ΕΠΙΤΡΟΠΗΣ ΑΞΙΟΛΟΓΗΣΗΣ"), [])


class Readers(unittest.TestCase):
    def read(self, kind, source, name, date=DATE):
        items = getattr(sources, "parse_" + kind)((FIXTURES / name).read_bytes(), SOURCE[source], date)
        self.assertTrue(items, f"{name}: nothing read")
        for it in items:
            self.assertTrue(it["title"] and it["url"].startswith("http"), it)
        return items

    def test_madgex_rss(self):
        # Nature's keyword RSS of 16 October 2026; Science Careers' RSS has the same (Madgex) format
        first = self.read("rss", "science", "nature.xml")[0]
        self.assertEqual(first["organisation"], "CHUM Microbiome Centre")      # from "Employer: Title"
        self.assertEqual(first["location"], "Montréal, Quebec (CA)")           # last line of the description
        self.assertNotIn("utm_", first["url"])

    def test_madgex_category_pages(self):
        items = self.read("madgex", "nature", "madgex_nature.html", DATE2)
        self.assertEqual(len(items), 3)
        first = items[0]
        self.assertTrue(first["organisation"].startswith("Shenzhen Institutes of Advanced Technology"))
        self.assertEqual(first["url"], "https://www.nature.com/naturecareers/job/12858264/global-recruitment-of-outstanding-young-talents/")
        self.assertEqual(first["posted"], "2026-11-10")                        # "1 day ago" on the run date
        the = self.read("madgex", "the", "madgex_the.html", DATE2)[0]
        self.assertEqual((the["organisation"], the["location"]), ("NEW YORK UNIVERSITY ABU DHABI", "Abu Dhabi, United Arab Emirates"))
        self.assertTrue(the["url"].startswith("https://www.timeshighereducation.com/unijobs/listing/417536/"))
        self.assertNotIn("LinkSource", the["url"])

    def test_madgex_pages_are_paths(self):
        src = SOURCE["nature"]
        self.assertEqual(sources.request_madgex(src, "postdoctoral", 1)[0], "https://www.nature.com/naturecareers/jobs/postdoctoral/")
        self.assertEqual(sources.request_madgex(src, "life-science/researcher", 3)[0],
                         "https://www.nature.com/naturecareers/jobs/life-science/researcher/3/")

    def test_jobs_ac_uk(self):
        first = self.read("jobs_ac_uk", "jobs-ac-uk", "jobs_ac_uk.html", DATE2)[0]
        self.assertEqual((first["organisation"], first["location"]), ("Durham University", "Durham"))
        self.assertEqual(first["notes"], "£39,560 to £46,970 per annum")
        self.assertEqual(first["summary"], "Department of Biosciences")
        self.assertEqual((first["posted"], first["deadline"]), ("2026-11-10", "2026-11-23"))   # "10 Nov", "23 Nov"

    def test_jobrxiv_search_feed(self):
        items = self.read("rss", "jobrxiv", "jobrxiv.xml", DATE2)
        self.assertEqual((items[1]["organisation"], items[1]["location"]), ("University of British Columbia Faculty", "Canada"))

    def test_fems_employer_after_dash(self):
        first = self.read("rss", "fems", "fems.xml", DATE2)[0]
        self.assertEqual(first["organisation"], "University of Birmingham")
        self.assertFalse(first["title"].endswith("Birmingham"))

    def test_mpg(self):
        self.assertTrue(all(i["organisation"] == "Max Planck Society" for i in self.read("rss", "mpg", "mpg.xml", DATE2)))

    def test_academic_jobs_online_rss1(self):
        first = self.read("rss", "ajo", "ajo.xml", DATE2)[0]                      # RSS 1.0 (RDF), the board's own fields
        self.assertEqual((first["organisation"], first["location"], first["deadline"]), ("SISSA", "Trieste, IT", "2026-12-23"))
        self.assertEqual(first["url"], "https://academicjobsonline.org/ajo/SISSA/Physics%20Area/33399")

    def test_euraxess_jobs(self):
        first = self.read("euraxess", "euraxess", "euraxess_jobs.html")[0]
        self.assertEqual((first["location"], first["notes"], first["deadline"]), ("Portugal", "R3", "2026-10-28"))

    def test_euraxess_funding(self):
        self.assertTrue(all(i["deadline"] for i in self.read("euraxess", "euraxess-funding", "euraxess_funding.html")))

    def test_embl_workday(self):
        self.assertTrue(self.read("workday", "embl", "embl.json")[0]["url"].startswith(SOURCE["embl"]["link_base"]))

    def test_jrc(self):
        items = self.read("jrc", "jrc", "jrc.json")
        self.assertFalse(any(i["title"].startswith("FG") for i in items))     # grade prefix moved out of the title

    def test_eu_funding_skips_passed_deadlines(self):
        items = self.read("eu_funding", "eu-funding", "eu_funding.json")
        self.assertEqual(len(items), 2)                                        # the third closed in 2024
        self.assertTrue(all(i["deadline"] >= DATE for i in items))

    def test_hcmr_greek_feed(self):
        self.assertEqual(len(self.read("rss", "hcmr", "hcmr.xml")), 3)


class Scoring(unittest.TestCase):
    scorer = Scorer(CFG)

    def best(self, **fields):
        m = self.scorer.score(row(**fields))
        return m[0][1] if m else None

    def test_listed_under_the_right_profile(self):
        self.assertEqual(self.best(title="Postdoctoral Position in Computational Metagenomics"), "microbial-genomics")
        self.assertEqual(self.best(title="Science for policy researcher for soil nutrients, LUCAS soil monitoring"),
                         "soil-conservation-policy")
        self.assertEqual(self.best(title="Postdoc: large language models for biodiversity literature"),
                         "biodiversity-informatics")
        self.assertEqual(self.best(title="Postdoc in ecological networks and food webs"), "complex-systems")
        self.assertEqual(self.best(kind="funding", sources="eu-funding", title="MSCA Postdoctoral Fellowships 2027"),
                         "funding")

    def test_left_out(self):
        self.assertIsNone(self.best(title="PhD position in soil metagenomics"))                   # excluded word
        self.assertIsNone(self.best(title="Postdoc, gut microbiome and cancer immunotherapy"))   # medicine
        self.assertIsNone(self.best(title="AI engineer, LLM systems for financial compliance"))
        self.assertIsNone(self.best(title="Postdoc in large language models for legal text"))   # `require` unmet
        self.assertIsNone(self.best(title="Researcher in soil microbiology", notes="R1"))       # first-stage only

    def test_postdoc_marked_r1_is_kept(self):
        # CNRS marked this postdoc R1 on EURAXESS (16 October 2026)
        self.assertEqual(self.best(title="Postdoctoral fixed-term contract - Theoretical approaches to the "
                                         "eco-evolutionary dynamics of food webs", notes="R1"), "complex-systems")
        self.assertIsNone(self.best(title="Laboratory animal technician"))                       # no keyword

    def test_platform_threshold(self):
        # JRC is scored on titles and unit names only, so one keyword is enough there
        self.assertIsNone(self.best(title="Project Officer", organisation="JRC, Land Resources"))
        self.assertEqual(self.best(title="Project Officer", organisation="JRC, Land Resources", sources="jrc"),
                         "soil-conservation-policy")


class Merging(unittest.TestCase):
    def test_same_title_two_platforms(self):
        title = "Science for policy researcher for soil nutrients, LUCAS soil monitoring"
        self.assertTrue(same_posting(row(title=title), row(title=title, sources="jrc")))

    def test_same_title_one_platform_is_two_postings(self):
        title = "ΠΡΟΣΚΛΗΣΗ ΕΚΔΗΛΩΣΗΣ ΕΝΔΙΑΦΕΡΟΝΤΟΣ ΓΙΑ ΤΗΝ ΠΡΟΣΛΗΨΗ 1 ΑΤΟΜΟΥ"
        self.assertFalse(same_posting(row(title=title, sources="hcmr"), row(title=title, sources="hcmr")))

    def test_short_titles_need_the_same_organisation(self):
        a = row(title="Bioinformatician", organisation="EMBL", sources="nature")
        self.assertFalse(same_posting(a, row(title="Bioinformatician", organisation="Ellison Institute", sources="science")))
        self.assertTrue(same_posting(row(title="Assistant Professor in Systems Biology", organisation="UC Irvine, Charlie Dunlop School"),
                                     row(title="Assistant Professor in Systems Biology", organisation="Charlie Dunlop School", sources="science")))


class Helpers(unittest.TestCase):
    def test_day_month_without_year(self):
        # jobs.ac.uk writes "10 Nov": placed on or before the run date, closing from a month before it on
        self.assertEqual(sources.day_month("10 Nov", "2026-11-11", closing=False), "2026-11-10")
        self.assertEqual(sources.day_month("23 Dec", "2026-01-05", closing=False), "2025-12-23")
        self.assertEqual(sources.day_month("5 Jan", "2026-12-20", closing=True), "2027-01-05")
        self.assertEqual(sources.day_month("8 Nov", "2026-11-11", closing=True), "2026-11-08")
        self.assertEqual(sources.day_month("soon", "2026-11-11", closing=True), "")

    def test_queries_per_platform(self):
        self.assertEqual(queries_for(SOURCE["nature"], CFG), SOURCE["nature"]["queries"])     # its own category pages
        self.assertIn("metagenomics", queries_for(SOURCE["jobrxiv"], CFG))                    # the profiles' queries
        self.assertNotIn("postdoctoral fellowship", queries_for(SOURCE["jobrxiv"], CFG))      # a funding query
        self.assertEqual(queries_for(SOURCE["mpg"], CFG), [""])                                # a whole feed

    def test_gzip_answer(self):
        # Academic Jobs Online sends gzip without being asked; the saved answer must be plain XML
        class Gzip(BaseHTTPRequestHandler):
            def do_GET(self):
                body = gzip.compress(b"<rss><channel></channel></rss>")
                self.send_response(200)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Gzip)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            status, body, err = http(f"http://127.0.0.1:{server.server_address[1]}/", CFG, tries=1)
            self.assertEqual((status, body, err), (200, b"<rss><channel></channel></rss>", ""))
        finally:
            server.shutdown()
            server.server_close()

    def test_dates(self):
        for text, iso in [("Wed, 14 Oct 2026 12:16:00 +0000", "2026-10-14"), ("28 Oct 2026 - 18:00 (Europe/Paris)", "2026-10-28"),
                          ("1 December 2026", "2026-12-01"), ("2027-01-14T00:00:00.000+0000", "2027-01-14"), ("soon", "")]:
            self.assertEqual(iso_date(text), iso)

    def test_watched_page_markers(self):
        w = next(w for w in CFG["watch"] if w["id"] == "sfi-postdoc")
        lines, note = watched_lines(FIXTURES / "watch_sfi.html", w)
        self.assertEqual(note, "")
        self.assertTrue(lines[0].startswith("Opens") and any(l.startswith("Deadline") for l in lines), lines)

    def test_web_page(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)       # port 0: any free port
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_address[1]}"

        def status(path):
            try:
                with urllib.request.urlopen(base + path, timeout=5) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                return e.code
        try:
            self.assertEqual([status(p) for p in ["/README.md", "/README.html", "/favicon.ico", "/config/profiles.toml",
                                                  "/no-such-page.md"]], [200, 200, 204, 200, 404])
        finally:
            server.shutdown()
            server.server_close()

    def test_markdown(self):
        html = markdown("## Jobs (1)\n\n- **[A \\[b\\] title](https://x.org/a?b=1&c=2)** · Org  \n  Greece · **deadline 2026-11-01**\n\n| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn('<h2 id="jobs-1">Jobs (1)</h2>', html)
        self.assertIn('<a href="https://x.org/a?b=1&amp;c=2">A [b] title</a>', html)
        self.assertIn('<span class="more">Greece · <strong>deadline 2026-11-01</strong></span>', html)
        self.assertIn("<td>1</td><td>2</td>", html)


if __name__ == "__main__":
    unittest.main()
