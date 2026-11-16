#!/usr/bin/env python3
"""One-off import: turn the captured Framer journal into Markdown posts + HTML templates.

  src/content/journal/<slug>.md   one file per post (frontmatter + markdown body)
  src/templates/post.html         the Framer post page with {{placeholders}}
  src/templates/index.html        the Framer journal listing with {{cards}}
  src/templates/card.html         one listing card with {{placeholders}}
"""
import html, json, os, re, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAP = os.path.join(ROOT, "_cap")
SITE = os.path.join(ROOT, "public")
OUT_MD = os.path.join(ROOT, "src", "content", "journal")
OUT_T = os.path.join(ROOT, "src", "templates")
CMS = os.path.join(SITE, "assets/framerusercontent/cms/maG4IPUoWpTdpmWNw7Ku/3YfsR9LIaylHjMx9vhLl/SFvw8dNv1-chunk-default-0.framercms")

# ---------- helpers ----------
def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def find_block(h, start):
    """Return end index (exclusive) of the element whose '<tag' starts at `start`."""
    tag = re.match(r"<([a-zA-Z0-9]+)", h[start:]).group(1)
    depth, i = 0, start
    pat = re.compile(rf"<(/?){tag}\b[^>]*?(/?)>")
    for m in pat.finditer(h, start):
        if m.group(2) == "/":
            continue
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.end()
    raise ValueError("unbalanced " + tag)

def el_by_attr(h, attr, start=0):
    """(start, end) of the first element after `start` carrying `attr` (e.g. data-framer-name="Body")."""
    i = h.find(attr, start)
    if i < 0:
        return None
    s = h.rfind("<", 0, i)
    return s, find_block(h, s)

def inner(h, s, e):
    gt = h.find(">", s) + 1
    close = h.rfind("</", gt, e)
    return h[gt:close]

def strip_tags(x):
    return html.unescape(re.sub(r"<[^>]+>", "", x)).strip()

def rich_to_md(x):
    """Framer rich text (p/h/ul/ol/a/strong/em/br) -> Markdown."""
    x = re.sub(r"<!--.*?-->", "", x, flags=re.S)
    out = []
    for m in re.finditer(r"<(p|h[1-6]|ul|ol|blockquote)\b[^>]*>(.*?)</\1>", x, flags=re.S):
        tag, body = m.group(1), m.group(2)
        def inline(t):
            t = re.sub(r"<br[^>]*>", "  \n", t)
            t = re.sub(r"<(strong|b)\b[^>]*>(.*?)</\1>", r"**\2**", t, flags=re.S)
            t = re.sub(r"<(em|i)\b[^>]*>(.*?)</\1>", r"*\2*", t, flags=re.S)
            t = re.sub(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", t, flags=re.S)
            t = re.sub(r"<[^>]+>", "", t)
            return html.unescape(t).strip()
        if tag in ("ul", "ol"):
            items = re.findall(r"<li\b[^>]*>(.*?)</li>", body, flags=re.S)
            for n, it in enumerate(items, 1):
                out.append(("- " if tag == "ul" else f"{n}. ") + inline(it))
            out.append("")
        elif tag.startswith("h"):
            t = inline(body)
            if t:
                out.append("#" * int(tag[1]) + " " + t + "\n")
        elif tag == "blockquote":
            out.append("> " + inline(body) + "\n")
        else:
            t = inline(body)
            if t:
                out.append(t + "\n")
    return "\n".join(out).strip() + "\n"

def yaml_str(s):
    return json.dumps(s, ensure_ascii=False)

# ---------- dates from the CMS chunk ----------
# Field values are stored as: <field id> 0c 00 00 00 <len byte> <utf-8 value>
dates = {}
if os.path.exists(CMS):
    raw = open(CMS, "rb").read()
    def values(field_id):
        out = []
        for m in re.finditer(re.escape(field_id.encode()), raw):
            i = m.end()
            if raw[i:i + 4] == b"\x0c\x00\x00\x00":
                n = raw[i + 4]
                out.append(raw[i + 5:i + 5 + n].decode("utf-8", "replace"))
        return out
    import datetime
    order = values("A9LPAA6_3")  # CMS order = listing order, newest first
    for slug, date in zip(order, values("WEFfBtnbp")):
        dates[slug] = date[:10]
    # The oldest 13 posts carry no date in Framer. Give them one day apart, before
    # the oldest dated post, so the listing keeps Framer's order.
    last = min(d for d in dates.values() if d)
    cur = datetime.date.fromisoformat(last)
    for slug in order:
        if not dates.get(slug):
            cur -= datetime.timedelta(days=1)
            dates[slug] = cur.isoformat()

# ---------- posts ----------
os.makedirs(OUT_MD, exist_ok=True)
posts = []
for fn in sorted(os.listdir(CAP)):
    if not fn.startswith("home_journal_") or not fn.endswith(".html"):
        continue
    cap = read(os.path.join(CAP, fn))
    slug = urllib.parse.unquote(re.search(r'<link rel="canonical" href="https://fabricate\.studio/journal/([^"]+)"', cap).group(1))
    h = read(os.path.join(SITE, "journal", slug, "index.html"))  # local-asset version
    body_html = h[h.find("<body"):]
    body_html = re.sub(r"<(style|script)\b.*?</\1>", "", body_html, flags=re.S)
    hdr = el_by_attr(body_html, 'data-framer-name="Title_mask"')
    title = strip_tags(inner(body_html, *hdr))
    img = re.search(r'data-framer-name="Image Wrapper".*?<img[^>]*src="([^"]+)"', body_html, flags=re.S)
    image = img.group(1) if img else ""
    sub = el_by_attr(body_html, 'data-framer-name="Subhead"')
    subtitle = strip_tags(inner(body_html, *sub)) if sub else ""
    bod = el_by_attr(body_html, 'data-framer-name="Body"')
    md = rich_to_md(inner(body_html, *bod))
    og = re.search(r'<meta property="og:image" content="([^"]+)"', h)
    date = dates.get(slug, "")
    posts.append(dict(slug=slug, title=title, subtitle=subtitle, image=image, date=date))
    fm = ["---", f"title: {yaml_str(title)}", f"subtitle: {yaml_str(subtitle)}", f"image: {yaml_str(image)}"]
    if date:
        fm.append(f"date: {date}")
    fm.append("---")
    with open(os.path.join(OUT_MD, slug + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + "\n\n" + md)
print(f"{len(posts)} posts written, {sum(1 for p in posts if p['date'])} with dates")
for p in posts:
    if not p["date"]:
        print("  no date:", p["slug"])

# ---------- templates ----------
# Markdown output has no Framer classes, so give the body wrapper equivalent styles.
BODY_CSS = """<style id="post-body">
.framer-1st8vd7{white-space:normal}
.framer-1st8vd7 :is(p,li){font-family:"Inter","Inter Placeholder",sans-serif;font-size:17px;font-weight:300;line-height:1.55em;letter-spacing:.02em;color:#fff;margin:0}
.framer-1st8vd7 p+p,.framer-1st8vd7 ul,.framer-1st8vd7 ol{margin-top:32px}
.framer-1st8vd7 ul,.framer-1st8vd7 ol{padding-left:1.4em}
.framer-1st8vd7 li+li{margin-top:8px}
.framer-1st8vd7 :is(h1,h2,h3,h4,h5,h6){font-family:"Inter","Inter Placeholder",sans-serif;font-weight:400;color:#fff;line-height:1.3em;margin:40px 0 16px}
.framer-1st8vd7 h2{font-size:28px}.framer-1st8vd7 h3{font-size:22px}.framer-1st8vd7 h4{font-size:18px}
.framer-1st8vd7 strong{font-weight:700}
.framer-1st8vd7 a{color:#fff;text-decoration:underline}
.framer-1st8vd7 img{max-width:100%;height:auto;display:block;margin:32px 0}
.framer-1st8vd7 blockquote{margin:32px 0;padding-left:20px;border-left:1px solid #999;font-style:italic}
</style>"""

os.makedirs(OUT_T, exist_ok=True)
# Framer's hamburger (Phone/Tablet nav variants) opens its menu with the runtime JS we dropped,
# so add a small overlay menu and a toggle of our own.
MENU = """<style id="mobile-menu-css">
#mobile-menu{position:fixed;inset:0;z-index:9999;background:rgb(22,22,12);display:none;flex-direction:column;justify-content:center;padding:40px}
#mobile-menu.open{display:flex}
#mobile-menu a{font-family:"Platypi","Platypi Placeholder",serif;font-weight:300;font-size:56px;line-height:1.1;color:#fff;text-decoration:none;margin:6px 0}
#mobile-menu .close{position:absolute;top:18px;right:24px;font:300 40px/1 "Inter",sans-serif;color:#fff;background:none;border:0;cursor:pointer}
</style>
<div id="mobile-menu" aria-hidden="true"><button class="close" aria-label="Close menu">&times;</button>
<a href="/about">About</a><a href="/works">Works</a><a href="/journal">Journal</a><a href="/#pricing-2">Pricing</a><a href="/contact">Contact</a></div>
<script>(()=>{const m=document.getElementById("mobile-menu");const t=o=>{m.classList.toggle("open",o);m.setAttribute("aria-hidden",String(!o))};
document.addEventListener("click",e=>{if(e.target.closest("nav .framer-1fcgn0o, nav [data-framer-name=Links][data-highlight]"))t(true);else if(e.target.closest("#mobile-menu .close, #mobile-menu a"))t(false)});})();</script>
"""
HIDDEN_CSS = "<style id=\"breakpoints\">@media(max-width: 809px){.hidden-1abh1od{display:none!important}}@media(min-width: 810px) and (max-width: 1439px){.hidden-36ol4n{display:none!important}}@media(min-width: 1440px){.hidden-1b9hlrl{display:none!important}}</style>"

def clean_page(h):
    h = re.sub(r'<script type="module"[^>]*data-framer-bundle="main"[^>]*></script>', "", h)
    h = h.replace("</body>", MENU + "</body>")
    h = re.sub(r'<meta name="framer-search-index"[^>]*>', "", h)
    h = re.sub(r'<meta name="generator"[^>]*>', '<meta name="generator" content="Astro">', h)
    h = re.sub(r'<link rel="canonical"[^>]*>', '<link rel="canonical" href="{{canonical}}">', h)
    h = re.sub(r'<link rel="alternate" hreflang[^>]*>', "", h)
    h = re.sub(r'<meta property="og:url"[^>]*>', '<meta property="og:url" content="{{canonical}}">', h)
    return h

# post template from the sample post
sample = "using-ai-to-redefine-performance-marketing"
p = next(x for x in posts if x["slug"] == sample)
h = clean_page(read(os.path.join(SITE, "journal", sample, "index.html")))
# The post page only renders the Desktop nav; the journal index renders Desktop/Phone/Tablet
# variants switched by CSS breakpoints. Transplant those (the nav CSS is already in both pages).
idx = read(os.path.join(SITE, "journal", "index.html"))
ib = idx[idx.find("<body"):]
cs, ce = el_by_attr(ib, 'class="framer-1n8cjt-container"')
navs = inner(ib, cs, ce)
ps = h.find("<nav ")
pe = find_block(h, ps)
h = h[:ps] + navs + h[pe:]
h = h.replace("</head>", HIDDEN_CSS + "</head>")
h = h.replace(html.escape(p["title"], quote=False), "{{title}}").replace(p["title"], "{{title}}")
h = h.replace(p["subtitle"], "{{subtitle}}")
img512 = re.sub(r"(\.[a-z0-9]+)$", r".17f51403\1", p["image"])
h = h.replace(img512, "{{image512}}").replace(p["image"], "{{image}}")
# body
s, e = el_by_attr(h, 'data-framer-name="Body"')
gt = h.find(">", s) + 1
close = h.rfind("</", gt, e)
h = h[:gt] + "{{body}}" + h[close:]
# prev / next blocks
s, e = el_by_attr(h, 'data-framer-name="Previous"')
h = h[:s] + "{{prev}}" + h[e:]
s, e = el_by_attr(h, 'data-framer-name="Next"')
h = h[:s] + "{{next}}" + h[e:]
# the page <title> / og:title carry the suffix
h = re.sub(r"<title>.*?</title>", "<title>{{pageTitle}}</title>", h, flags=re.S)
h = re.sub(r'(<meta (?:property="og:title"|name="twitter:title") content=")[^"]*"', r"\1{{pageTitle}}\"", h)
h = re.sub(r'(<meta (?:property="og:description"|name="twitter:description"|name="description") content=")[^"]*"', r"\1{{description}}\"", h)
h = re.sub(r'(<meta (?:property="og:image"|name="twitter:image") content=")[^"]*"', r"\1{{ogImage}}\"", h)
h = h.replace("</head>", BODY_CSS + "</head>")
with open(os.path.join(OUT_T, "post.html"), "w", encoding="utf-8") as f:
    f.write(h)
# prev/next snippets (the original inner markup, parameterised)
src = read(os.path.join(SITE, "journal", sample, "index.html"))
s, e = el_by_attr(src, 'data-framer-name="Previous"')
prev = src[s:e]
prev = re.sub(r'href="[^"]*"', 'href="{{href}}"', prev)
prev = re.sub(r">‹ [^<]*<", ">‹ {{title}}<", prev)
s, e = el_by_attr(src, 'data-framer-name="Next"')
nxt = src[s:e]
nxt = re.sub(r'href="[^"]*"', 'href="{{href}}"', nxt)
nxt = re.sub(r">([^<]*) ›<", ">{{title}} ›<", nxt)
with open(os.path.join(OUT_T, "prev.html"), "w") as f: f.write(prev)
with open(os.path.join(OUT_T, "next.html"), "w") as f: f.write(nxt)

# index template + card
h = clean_page(read(os.path.join(SITE, "journal", "index.html")))
cards = [m.start() for m in re.finditer(r'<div class="framer-sc936u">', h)]
first_s, first_e = cards[0], find_block(h, cards[0])
last_e = find_block(h, cards[-1])
card = h[first_s:first_e]
c0 = posts_by = {x["slug"]: x for x in posts}
m = re.search(r'href="/journal/([^"]+)"', card)
c = posts_by[m.group(1)]
card = card.replace(f'href="/journal/{c["slug"]}"', 'href="{{href}}"')
card = card.replace(html.escape(c["title"], quote=False), "{{title}}").replace(c["title"], "{{title}}")
card = card.replace(c["subtitle"], "{{subtitle}}")
cimg = re.search(r'src="([^"]+)"', card).group(1)
cimg512 = re.sub(r"(\.[a-z0-9]+)$", r".17f51403\1", cimg)
card = card.replace(cimg512, "{{image512}}").replace(cimg, "{{image}}")
h = h[:first_s] + "{{cards}}" + h[last_e:]
h = re.sub(r"<title>.*?</title>", "<title>{{pageTitle}}</title>", h, flags=re.S)
with open(os.path.join(OUT_T, "index.html"), "w", encoding="utf-8") as f: f.write(h)
with open(os.path.join(OUT_T, "card.html"), "w", encoding="utf-8") as f: f.write(card)
print("templates written; placeholders in card:", re.findall(r"{{\w+}}", card).__len__(), "cards in original:", len(cards))
