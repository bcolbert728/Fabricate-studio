#!/usr/bin/env python3
"""Turn the captured Framer HTML into a self-contained static site in ../site."""
import hashlib, os, re, sys, urllib.request, urllib.parse, html as htmlmod
from concurrent.futures import ThreadPoolExecutor

CAP = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(CAP), "public")
HOSTS = ("framerusercontent.com", "app.framerstatic.com", "fonts.gstatic.com")
URL_RE = re.compile(r'https://(?:' + '|'.join(re.escape(h) for h in HOSTS) + r')/[^\s"\'()<>\\]+')

seen = {}          # remote url -> local root-relative path
queue = []

def local_path(url):
    if url in seen:
        return seen[url]
    u = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(u.path).lstrip("/")
    if u.query:
        base, ext = os.path.splitext(path)
        path = f"{base}.{hashlib.md5(u.query.encode()).hexdigest()[:8]}{ext}"
    rel = "/assets/" + u.netloc.split(".")[0] + "/" + path
    seen[url] = rel
    queue.append(url)
    return rel

def fetch(url):
    dest = OUT + seen[url]
    if os.path.exists(dest):
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            f.write(r.read())
    except Exception as e:
        print("FAIL", url, e, file=sys.stderr)
        return None
    return dest

def rewrite_text(text):
    return URL_RE.sub(lambda m: local_path(htmlmod.unescape(m.group(0))), text)

STRIP_SCRIPTS = [
    r'<script[^>]*analytics\.ahrefs\.com[^>]*>.*?</script>',
    r'<script[^>]*googletagmanager\.com[^>]*></script>',
    r'<script>\s*window\.dataLayer.*?</script>',
    r'<script[^>]*events\.framer\.com[^>]*></script>',
]

def process_html(src):
    with open(src, encoding="utf-8") as f:
        h = f.read()
    # route from the canonical URL (capture filenames were truncated for long slugs)
    m = re.search(r'<link rel="canonical" href="https://fabricate\.studio/?([^"]*)"', h)
    route = urllib.parse.unquote(m.group(1)) if m else os.path.basename(src)[5:-5].replace("_", "/")
    dest_dir = os.path.join(OUT, route) if route else OUT
    for pat in STRIP_SCRIPTS:
        h = re.sub(pat, "", h, flags=re.S)
    # Framer HTML escapes & as &amp; in attributes; handle both spellings of srcset URLs
    h = re.sub(r'https://(?:framerusercontent\.com|app\.framerstatic\.com|fonts\.gstatic\.com)/[^\s"\'()<>\\]+',
               lambda m: local_path(htmlmod.unescape(m.group(0))), h)
    # internal links -> root-relative
    h = h.replace('href="https://fabricate.studio/', 'href="/').replace('href="https://fabricate.studio"', 'href="/"')
    # Framer writes links relative to the slash-less page URL ("../works" from /journal/post).
    # Hosts serve /journal/post/ (trailing slash) for folder/index.html, which would break them,
    # so resolve every relative href to a root-relative one.
    page_url = "https://x/" + route
    def abs_href(m):
        target = urllib.parse.urljoin(page_url, m.group(1))
        return 'href="' + target[len("https://x"):] + '"'
    h = re.sub(r'href="(\.\.?/[^"]*)"', abs_href, h)
    h = h.replace('href="/"', 'href="/"')
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(h)

def main():
    pages = sorted(p for p in os.listdir(CAP) if p.startswith("home_") and p.endswith(".html"))
    for p in pages:
        process_html(os.path.join(CAP, p))
    print(f"{len(pages)} pages written")
    os.makedirs(os.path.join(OUT, "assets"), exist_ok=True)
    with open(os.path.join(OUT, "assets", "editor-stub.mjs"), "w") as f:
        f.write("export const createEditorBar = () => () => null;\n")
    # download assets; JS/CSS/JSON may reference further assets -> loop until the queue drains
    done = 0
    while done < len(queue):
        batch = queue[done:]
        done = len(queue)
        with ThreadPoolExecutor(16) as ex:
            results = list(ex.map(fetch, batch))
        for url, dest in zip(batch, results):
            if dest and dest.endswith((".mjs", ".js", ".css", ".json")):
                with open(dest, encoding="utf-8", errors="replace") as f:
                    t = f.read()
                t2 = rewrite_text(t)
                # Framer's editor bar is only for logged-in Framer users; stub it out
                t2 = t2.replace('"https://edit.framer.com/init.mjs"', '"/assets/editor-stub.mjs"')
                # CMS data: new URL("./X.framercms", "https://framerusercontent.com/modules/a/b/X.js")
                # then .replace("/modules/","/cms/"). Keep the base absolute and fetch the cms chunk.
                def cms(m):
                    name, base = m.group(1), m.group(2)
                    remote_dir = base.replace("/assets/framerusercontent/", "https://framerusercontent.com/").replace("/modules/", "/cms/").rsplit("/", 1)[0]
                    local_path(remote_dir + "/" + name)
                    return f'new URL("./{name}",location.origin+"{base.replace("/modules/", "/cms/")}")'
                t2 = re.sub(r'new URL\("\./([^"]+\.framercms)","(/assets/framerusercontent/modules/[^"]+)"\)', cms, t2)
                # Framer's CDN serves byte ranges via "?range=a-b,c-d" and returns exactly those
                # bytes. Static hosts ignore the query and return the whole file, so slice it here.
                t2 = t2.replace(
                    'if(d.length!==i)throw Error("Request failed: Unexpected response length");',
                    'if(d.length!==i){let f=d;d=new Uint8Array(i);let q=0;for(let c of r){d.set(f.subarray(c.from,c.to),q);q+=c.to-c.from}}')
                # follow relative "./x.mjs" imports to sibling chunks
                base = url.rsplit("/", 1)[0] + "/"
                for rel in set(re.findall(r'["\']\./([A-Za-z0-9_.-]+\.mjs)["\']', t2)):
                    local_path(base + rel)
                if t2 != t:
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(t2)
        print(f"downloaded {done} assets")

if __name__ == "__main__":
    main()
