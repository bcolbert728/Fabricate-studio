import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

// One Markdown file per post in src/content/journal/<slug>.md
const journal = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/journal' }),
  schema: z.object({
    title: z.string(),
    subtitle: z.string().default(''),
    image: z.string(),                 // e.g. /images/journal/my-post.jpg (served from public/)
    date: z.coerce.date(),
    description: z.string().optional(), // meta description; falls back to subtitle
    draft: z.boolean().default(false),  // true = not built
  }),
});

export const collections = { journal };
