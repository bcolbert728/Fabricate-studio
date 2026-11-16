// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://fabricate.studio',
  trailingSlash: 'ignore',
  build: { format: 'directory' },
});
