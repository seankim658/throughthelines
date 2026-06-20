import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
import sirv from 'sirv';
import { fileURLToPath } from 'node:url';

const derivedDir = fileURLToPath(new URL('../../data/derived', import.meta.url));

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit(),
		{
			name: 'serve-derived-dev',
			apply: 'serve', // dev/preview only
			configureServer(server) {
				const serveDerived = sirv(derivedDir, { dev: true, etag: true });
				server.middlewares.use('/derived', (req, res, next) => {
					if (req.url && /^\/basemap\/.+\.pmtiles$/.test(req.url)) {
						req.url = '/basemaps/basemap.pmtiles';
					}
					serveDerived(req, res, next);
				});
			}
		}
	]
});
