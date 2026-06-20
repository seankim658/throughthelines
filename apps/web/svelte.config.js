import adapter from '@sveltejs/adapter-static';
import { mdsvex } from 'mdsvex';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import { escapeSvelte } from 'mdsvex';
import { codeToHtml } from 'shiki';

async function highlighter(code, lang) {
	const html = await codeToHtml(code, {
		lang: lang || 'text',
		themes: { light: 'vitesse-light', dark: 'vitesse-dark' },
		defaultColor: false,
		transformers: [
			{
				pre(node) {
					delete node.properties.tabindex;
				}
			}
		]
	});
	return escapeSvelte(html);
}

const mdsvexConfig = {
	extensions: ['.svx'],
	highlight: { highlighter },
	remarkPlugins: [remarkGfm],
	rehypePlugins: [rehypeSlug, [rehypeAutolinkHeadings, { behavior: 'wrap' }]]
};

/** @type {import('@sveltejs/kit').Config} */
const config = {
	extensions: ['.svelte', '.svx'],
	preprocess: [mdsvex(mdsvexConfig)],
	compilerOptions: {
		// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
		runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true)
	},
	kit: {
		// adapter-auto only supports some environments, see https://svelte.dev/docs/kit/adapter-auto for a list.
		// If your environment is not supported, or you settled on a specific environment, switch out the adapter.
		// See https://svelte.dev/docs/kit/adapters for more information about adapters.
		adapter: adapter({
			fallback: 'index.html'
		})
	}
};

export default config;
