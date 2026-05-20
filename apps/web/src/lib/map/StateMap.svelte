<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import { PMTiles, Protocol } from 'pmtiles';
	import 'maplibre-gl/dist/maplibre-gl.css';

	// Matches the tippecanoe `-l` flag in pipeline/src/pipeline/tiles/build.py
	const SOURCE_LAYER = 'districts';

	const SOURCE_ID = 'districts';
	const FILL_LAYER_ID = 'districts-fill';
	const LINE_LAYER_ID = 'districts-line';
	const HIGHLIGHT_FILL_LAYER_ID = 'districts-highlight-fill';
	const HIGHLIGHT_LINE_LAYER_ID = 'districts-highlight-line';
	const LABEL_LAYER_ID = 'districts-label';

	const GLYPHS_URL = '/fonts/{fontstack}/{range}.pbf';

	let {
		tilesUrl,
		activePlanId,
		activeDistrict
	}: { tilesUrl: string; activePlanId: string; activeDistrict: number | null } = $props();

	let container: HTMLDivElement;
	let map = $state<maplibregl.Map | null>(null);

	function planFilter(planId: string): maplibregl.FilterSpecification {
		return ['==', ['get', 'plan_id'], planId];
	}

	function highlightFilter(
		planId: string,
		district: number | null
	): maplibregl.FilterSpecification {
		if (district === null) {
			return ['==', ['get', 'district'], -1];
		}
		return ['all', ['==', ['get', 'plan_id'], planId], ['==', ['get', 'district'], district]];
	}

	onMount(() => {
		const protocol = new Protocol();
		maplibregl.addProtocol('pmtiles', protocol.tile);

		const pmtiles = new PMTiles(tilesUrl);
		protocol.add(pmtiles);

		let created: maplibregl.Map | null = null;
		let cancelled = false;

		(async () => {
			try {
				const header = await pmtiles.getHeader();
				if (cancelled) return;

				const styles = getComputedStyle(document.documentElement);
				const accent = styles.getPropertyValue('--accent').trim() || '#b8541f';
				const lineColor = styles.getPropertyValue('--ink-secondary').trim() || '#4a453e';
				const inkPrimary = styles.getPropertyValue('--ink-primary').trim() || '#1c1a17';
				const surfacePage = styles.getPropertyValue('--surface-page').trim() || '#faf8f5';

				const newMap = new maplibregl.Map({
					container,
					style: {
						version: 8,
						glyphs: GLYPHS_URL,
						sources: {
							[SOURCE_ID]: {
								type: 'vector',
								url: `pmtiles://${tilesUrl}`
							}
						},
						layers: [
							{
								id: FILL_LAYER_ID,
								source: SOURCE_ID,
								'source-layer': SOURCE_LAYER,
								type: 'fill',
								filter: planFilter(activePlanId),
								paint: {
									'fill-color': accent,
									'fill-opacity': 0.12
								}
							},
							{
								id: LINE_LAYER_ID,
								source: SOURCE_ID,
								'source-layer': SOURCE_LAYER,
								type: 'line',
								filter: planFilter(activePlanId),
								paint: {
									'line-color': lineColor,
									'line-width': 0.75
								}
							},
							{
								id: HIGHLIGHT_FILL_LAYER_ID,
								source: SOURCE_ID,
								'source-layer': SOURCE_LAYER,
								type: 'fill',
								filter: highlightFilter(activePlanId, activeDistrict),
								paint: {
									'fill-color': accent,
									'fill-opacity': 0.35
								}
							},
							{
								id: HIGHLIGHT_LINE_LAYER_ID,
								source: SOURCE_ID,
								'source-layer': SOURCE_LAYER,
								type: 'line',
								filter: highlightFilter(activePlanId, activeDistrict),
								paint: {
									'line-color': accent,
									'line-width': 2.5
								}
							},
							{
								id: LABEL_LAYER_ID,
								source: SOURCE_ID,
								'source-layer': 'labels',
								type: 'symbol',
								filter: ['==', ['get', 'plan_id'], activePlanId],
								layout: {
									'text-field': ['to-string', ['get', 'district']],
									'text-font': ['Noto Sans Regular'],
									'text-size': 14
								},
								paint: {
									'text-color': inkPrimary,
									'text-halo-color': surfacePage,
									'text-halo-width': 1.5
								}
							}
						]
					},
					bounds: [
						[header.minLon, header.minLat],
						[header.maxLon, header.maxLat]
					],
					fitBoundsOptions: { padding: 20 }
				});
				created = newMap;

				newMap.on('load', () => {
					if (cancelled) return;
					map = newMap;
				});
			} catch (err) {
				console.error('StateMap: failed to load PMTiles', err);
			}
		})();

		return () => {
			cancelled = true;
			created?.remove();
			map = null;
			maplibregl.removeProtocol('pmtiles');
		};
	});

	$effect(() => {
		if (map === null) return;
		const planF = planFilter(activePlanId);
		const highlightF = highlightFilter(activePlanId, activeDistrict);
		map.setFilter(FILL_LAYER_ID, planF);
		map.setFilter(LINE_LAYER_ID, planF);
		map.setFilter(HIGHLIGHT_FILL_LAYER_ID, highlightF);
		map.setFilter(HIGHLIGHT_LINE_LAYER_ID, highlightF);
		map.setFilter(LABEL_LAYER_ID, ['==', ['get', 'plan_id'], activePlanId]);
	});
</script>

<div bind:this={container} class="bg-surface-sunken h-[520px] w-full rounded"></div>
