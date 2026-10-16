"""The local web page: shows the Markdown files of this folder as HTML.

    python3 scripts/serve.py [--port=8000] [--open]

then open http://127.0.0.1:8000 (--open does it for you). Only this computer can reach it
(it listens on 127.0.0.1). Pages are converted when asked for, so the output of a run that
finishes while the server is up shows on the next reload. Other files (CSV, TOML, PDF) are
served as they are; a failed request is printed in the terminal. markdown() below knows the subset that the scripts and the README
use: headings, paragraphs, lists, quotes, tables, code, links, bold and italics.
"""
import html
import re
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from common import ROOT, flag, say

ITEM = r"([-*]|\d+\.) "


def inline(text):
    """Code, links, bold and italics inside a line; everything else is escaped."""
    stash = []

    def keep(fragment):
        stash.append(fragment)
        return f"\x00{len(stash) - 1}\x00"

    text = re.sub(r"\\([\\`*_\[\]|<>()#!-])", lambda m: keep(html.escape(m[1])), text)
    text = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{html.escape(m[1])}</code>"), text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{m[2].replace(chr(34), "%22")}">{m[1]}</a>', text)
    text = re.sub(r"&lt;(https?://.+?)&gt;", r'<a href="\1">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m[1])], text)


def lines_html(lines, item=False):
    """The lines of a paragraph or list item. A line ending in two spaces breaks the line;
    in a list item the lines after the first are set smaller; '> ' lines are quotes."""
    out, quote = [], []
    for n, line in enumerate(lines):
        if line.startswith("> "):
            quote.append(inline(line[2:]))
            continue
        if quote:
            out.append("<blockquote>" + "<br>".join(quote) + "</blockquote>")
            quote = []
        text = inline(line.strip())
        out.append(text if n == 0 or not item else f'<span class="more">{text}</span>')
        if not item and line.endswith("  ") and n < len(lines) - 1:
            out.append("<br>")
    if quote:
        out.append("<blockquote>" + "<br>".join(quote) + "</blockquote>")
    return " ".join(out)


def table(rows):
    cells = [[inline(c.strip()) for c in re.split(r"(?<!\\)\|", r.strip()[1:-1] if r.strip().endswith("|") else r.strip()[1:])] for r in rows]
    body = [r for r in cells[1:] if not all(re.fullmatch(r":?-{3,}:?", c) for c in r)]
    return ("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cells[0]) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")


def markdown(md):
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            j = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("```")), len(lines))
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1
        elif line.startswith("    "):
            j = i
            while j < len(lines) and (lines[j].startswith("    ") or not lines[j].strip()):
                j += 1
            out.append("<pre><code>" + html.escape("\n".join(l[4:] for l in lines[i:j]).rstrip()) + "</code></pre>")
            i = j
        elif m := re.match(r"(#{1,4}) (.*)", line):
            slug = re.sub(r"[^a-z0-9]+", "-", m[2].lower()).strip("-")
            out.append(f'<h{len(m[1])} id="{slug}">{inline(m[2])}</h{len(m[1])}>')
            i += 1
        elif line.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append(table(lines[i:j]))
            i = j
        elif re.match(ITEM, line):
            tag, items = "ol" if line[0].isdigit() else "ul", []
            while i < len(lines) and (re.match(ITEM, lines[i]) or (items and lines[i].startswith("  "))):
                if re.match(ITEM, lines[i]):
                    items.append([re.sub("^" + ITEM, "", lines[i])])
                else:
                    items[-1].append(lines[i][2:])
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{lines_html(it, item=True)}</li>" for it in items) + f"</{tag}>")
        elif line.startswith(">"):
            j = i
            while j < len(lines) and lines[j].startswith(">"):
                j += 1
            out.append("<blockquote>" + lines_html([l[1:].strip() for l in lines[i:j]]) + "</blockquote>")
            i = j
        elif line.strip() in ("---", "***"):
            out.append("<hr>")
            i += 1
        elif not line.strip():
            i += 1
        else:
            j = i
            while j < len(lines) and lines[j].strip() and not re.match(r"(#{1,4} |```|\||>|" + ITEM + ")", lines[j]):
                j += 1
            out.append("<p>" + lines_html(lines[i:j]) + "</p>")
            i = j
    return "\n".join(out)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%2317695a'/%3E%3C/svg%3E">
<style>
:root {{ --bg: #fbfaf7; --fg: #1f2328; --muted: #5f6872; --line: #e2dfd6; --code: #f0ede6; --accent: #17695a; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #15171a; --fg: #e7e6e2; --muted: #a2a9b0; --line: #2d3137; --code: #202328; --accent: #73c7b1; }}
}}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
nav {{ position: sticky; top: 0; background: var(--bg); border-bottom: 1px solid var(--line); padding: .65rem 1rem; display: flex; gap: 1.3rem; flex-wrap: wrap; }}
nav a {{ color: var(--fg); text-decoration: none; font-weight: 600; }}
nav a:hover {{ color: var(--accent); }}
main {{ max-width: 56rem; margin: 0 auto; padding: .5rem 1rem 4rem; }}
h1 {{ font-size: 1.65rem; margin: 1rem 0 .4rem; }}
h2 {{ font-size: 1.2rem; margin: 2.2rem 0 .6rem; padding-bottom: .25rem; border-bottom: 1px solid var(--line); }}
a {{ color: var(--accent); }}
ul, ol {{ padding-left: 1.2rem; }}
li {{ margin: .85rem 0; }}
li .more {{ display: block; color: var(--muted); font-size: .9rem; }}
li .more strong {{ color: var(--fg); }}
blockquote {{ margin: .4rem 0; padding: .1rem .8rem; border-left: 3px solid var(--line); color: var(--muted); }}
table {{ border-collapse: collapse; display: block; overflow-x: auto; font-size: .92rem; }}
th, td {{ border-bottom: 1px solid var(--line); padding: .35rem .7rem .35rem 0; text-align: left; vertical-align: top; }}
code, pre {{ font: 13px/1.45 ui-monospace, Menlo, Consolas, monospace; }}
code {{ background: var(--code); padding: .05rem .25rem; border-radius: 4px; }}
pre {{ background: var(--code); padding: .75rem; overflow-x: auto; border-radius: 6px; }}
pre code {{ padding: 0; }}
</style></head>
<body><nav><a href="/">Index</a><a href="/open.md">Open now</a><a href="/config/profiles.toml">Profiles &amp; platforms</a><a href="/README.md">How it works</a></nav>
<main>
{body}
</main></body></html>
"""


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".toml": "text/plain; charset=utf-8",
                      ".csv": "text/plain; charset=utf-8", ".py": "text/plain; charset=utf-8"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/favicon.ico":          # browsers ask for a tab icon; the pages carry their own
            self.send_response(204)
            return self.end_headers()
        file = (ROOT / (path.lstrip("/") or "index.md")).resolve()
        if file.suffix == ".html":          # /index.html, /open.html: the Markdown page of that name
            file = file.with_suffix(".md")
        if not file.is_relative_to(ROOT) or not file.exists():
            return self.page(f"# Not found\n\nThere is no `{path}` here: go to the [index](/) or [Open now](/open.md). "
                             "If the index itself is missing, run `python3 scripts/run.py` first.", 404)
        if file.suffix != ".md" or not file.is_file():
            return super().do_GET()
        self.page(file.read_text(encoding="utf-8"))

    def page(self, text, status=200):
        title = next((l[2:] for l in text.splitlines() if l.startswith("# ")), "job-postings")
        body = PAGE.format(title=html.escape(re.sub(r"[\\*`\[\]]", "", title)), body=markdown(text)).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_request(self, code="-", size="-"):
        """Print failed requests only, so that a problem names its address."""
        if isinstance(code, int) and code >= 400:
            say(f"{code} {self.path}")

    def log_message(self, *args):
        pass


def main():
    port = flag("port")
    port = int(port[0]) if isinstance(port, list) else 8000
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        raise SystemExit(f"Port {port} is in use: is the server already running in another terminal? "
                         f"Use that one, or start this one with --port={port + 1}")
    # 127.0.0.1 rather than localhost: localhost may resolve to IPv6 (::1) first, where nothing listens
    url = f"http://127.0.0.1:{port}/"
    say(f"Serving {ROOT} at {url}  (Ctrl-C stops)")
    if flag("open"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
