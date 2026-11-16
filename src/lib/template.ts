import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import type { CollectionEntry } from 'astro:content';

export type Post = CollectionEntry<'journal'>;

const SITE = 'https://fabricate.studio';
const SUFFIX = ' - Fabricate.Studio - Generative AI Retail, Product and Brand marketing';

export const tpl = (name: string) =>
  readFileSync(join(process.cwd(), 'src/templates', `${name}.html`), 'utf8');

export const fill = (t: string, vars: Record<string, string>) =>
  t.replace(/{{(\w+)}}/g, (_, k) => vars[k] ?? '');

export const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** Newest first, drafts excluded. */
export const sortPosts = (posts: Post[]) =>
  posts.filter((p) => !p.data.draft).sort((a, b) => b.data.date.getTime() - a.data.date.getTime());

/** The Framer export kept a 512px variant next to each image as <name>.17f51403.<ext>; use it when present. */
export const image512 = (image: string) => {
  const small = image.replace(/(\.[a-z0-9]+)$/i, '.17f51403$1');
  return existsSync(join(process.cwd(), 'public', small)) ? small : image;
};

export const postVars = (p: Post) => ({
  href: `/journal/${p.id}`,
  title: esc(p.data.title),
  subtitle: esc(p.data.subtitle),
  image: p.data.image,
  image512: image512(p.data.image),
  pageTitle: esc(p.data.title + SUFFIX),
  description: esc(p.data.description ?? p.data.subtitle),
  ogImage: SITE + p.data.image,
  canonical: `${SITE}/journal/${p.id}`,
});
