# fabricate.studio

Self-hosted version of fabricate.studio, exported from Framer on 2026-11-16 and turned into an
[Astro](https://astro.build) site so the journal can keep growing without Framer.

```
public/                  the Framer export, served as-is (home, about, works, services, contact, assets)
src/content/journal/     one Markdown file per journal post  ← this is what you edit
src/templates/           the journal page shells, lifted from the Framer export
src/pages/journal/       Astro pages that pour the Markdown into those shells
tools/import_framer.py   one-off importer that produced the posts and templates
_cap/                    raw Framer capture + mirror.py (only needed to re-export; not deployed)
```

## Adding a journal post

Create `src/content/journal/<slug>.md`. The file name becomes the URL (`/journal/<slug>`).

```markdown
---
title: "Why AI Product Imagery Converts."
subtitle: "A short deck under the headline, shown on the post and in the listing."
image: "/images/journal/ai-product-imagery.jpg"
date: 2026-11-20
---

First paragraph…

## A heading inside the post

More paragraphs, **bold**, *italic*, [links](https://example.com), lists and images all work.
```

- Put the cover image in `public/images/journal/` (any size; 1200px wide is plenty). Portrait or landscape both work — it is cropped to the hero.
- `date` controls ordering (newest first) and prev/next links. Posts are not shown with a date.
- Add `draft: true` to keep a post out of the build.
- Optional `description:` sets the meta description; otherwise the subtitle is used.

Or just tell Claude: "add a journal post about X" and it writes the file.

## Editing other pages

Home, about, works, case studies, services and contact are static HTML in `public/`.
Text edits can be made straight in those files (search for the sentence). Adding a new case
study is not supported this way yet; ask Claude to convert the works section to Markdown
like the journal if you need that.

## Run locally

Node 22+ is required (installed in `~/.local/node` on this Mac).

```bash
npm install
npm run dev        # http://localhost:4321, live-reloads as you edit
npm run build      # writes the finished site to dist/
```

## Deploy

The site is a plain `dist/` folder, so any static host works. Recommended: **Cloudflare Pages**
(free, unlimited bandwidth — the export has ~280 MB of video).

Connect this Git repo in the Cloudflare dashboard with:
- Build command: `npm run build`
- Output directory: `dist`

Every push to `main` then rebuilds and publishes the site in about a minute.
Then point the `fabricate.studio` DNS at Cloudflare and remove the Framer records.

Netlify (publish dir `dist`) and Vercel work the same way.

## Things to know

- **Contact form** posts to Formspark, not Framer, so it keeps working as long as the Formspark account exists.
- **Analytics**: Google Tag Manager (`GTM-52KFN2ZV`) and the Apollo website tracker are still in every page. Framer's own analytics, Ahrefs and the `gtag` snippet were removed.
- Journal pages no longer load the Framer runtime. The hover micro-animations and the listing's
  "load more" are gone (all posts are listed); everything else — fonts, layout, SEO tags, URLs — is the same.
- The 13 oldest posts had no date in Framer; they were given consecutive dates before 2025-05-27 to keep their order.
- One SVG referenced on one journal page already 404s on Framer and is missing here too.
- `_cap/mirror.py` can re-export the Framer site while it is still live (run the capture loop in the file header first).
