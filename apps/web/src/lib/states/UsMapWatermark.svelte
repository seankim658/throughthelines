<script lang="ts">
	import type { Manifest } from '$lib/manifest/types';
	import { classifyCoverage, type Coverage } from './states';
	import { MAP_VIEWBOX, STATE_PATHS } from './map-paths';

	let { manifest }: { manifest: Manifest } = $props();

	// Render order matters: state borders are shared edges, so adjacent
	// paths overdraw each other along common pixels. Drawing not_yet first,
	// then planned, then covered ensures the stronger treatment always
	// wins on a shared border.
	const RENDER_ORDER: Record<Coverage, number> = {
		not_yet: 0,
		planned: 1,
		covered: 2
	};

	const sortedStates = $derived(
		Object.entries(STATE_PATHS)
			.map(([code, d]) => ({ code, d, coverage: classifyCoverage(code, manifest) }))
			.sort((a, b) => RENDER_ORDER[a.coverage] - RENDER_ORDER[b.coverage])
	);

	function pathClasses(coverage: Coverage): string {
		if (coverage === 'covered') {
			return 'fill-accent [fill-opacity:0.85]';
		}
		if (coverage === 'planned') {
			return 'fill-none stroke-line-strong [stroke-width:1.25]';
		}
		return 'fill-none stroke-line-subtle [stroke-width:1]';
	}
</script>

<svg
	viewBox="0 0 {MAP_VIEWBOX.width} {MAP_VIEWBOX.height}"
	xmlns="http://www.w3.org/2000/svg"
	aria-hidden="true"
	class="block h-auto w-full"
>
	{#each sortedStates as { code, d, coverage } (code)}
		<path {d} class={pathClasses(coverage)} />
	{/each}
</svg>
