<script lang="ts">
	import { onMount } from 'svelte';
	import maplibregl from 'maplibre-gl';
	import { PMTiles, Protocol } from 'pmtiles';
	import { layers as protomapsLayers, namedFlavor } from '@protomaps/basemaps';
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
	const SPRITE_URL = '/sprites/v4/light';
	const BASEMAP_SOURCE_ID = 'basemap';

	let {
		tilesUrl,
		basemapUrl,
		activePlanId,
		activeDistrict,
		marker,
		showBasemap = true
	}: {
		tilesUrl: string;
		basemapUrl?: string | null;
		activePlanId: string;
		activeDistrict: number | null;
		marker?: { lat: number; lng: number } | null;
		showBasemap?: boolean;
	} = $props();

	let container: HTMLDivElement;
	let map = $state<maplibregl.Map | null>(null);
	let addressMarker: maplibregl.Marker | null = null;
	let initialBounds: [[number, number], [number, number]] | null = null;

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

	function recenter(): void {
		if (map === null || initialBounds === null) return;
		map.fitBounds(initialBounds, { padding: 20, duration: 600 });
	}

	onMount(() => {
		const protocol = new Protocol();
		maplibregl.addProtocol('pmtiles', protocol.tile);

		const pmtiles = new PMTiles(tilesUrl);
		protocol.add(pmtiles);

		if (basemapUrl) {
			const basemapPmtiles = new PMTiles(basemapUrl);
			protocol.add(basemapPmtiles);
		}

		let created: maplibregl.Map | null = null;
		let cancelled = false;

		(async () => {
			try {
				const header = await pmtiles.getHeader();
				if (cancelled) return;

				const styles = getComputedStyle(document.documentElement);
				const accent = styles.getPropertyValue('--accent').trim() || '#b8541f';
				const lineColor = '#4a453e';
				// const inkPrimary = styles.getPropertyValue('--ink-primary').trim() || '#1c1a17';
				// const surfacePage = styles.getPropertyValue('--surface-page').trim() || '#faf8f5';
				const LABEL_INK = '#1c1a17'; // --ink-primary (light)
				const LABEL_HALO = '#faf8f5'; // --surface-page (light)

				const basemapSources: maplibregl.StyleSpecification['sources'] = basemapUrl
					? {
							[BASEMAP_SOURCE_ID]: {
								type: 'vector',
								url: `pmtiles://${basemapUrl}`,
								attribution:
									'<a href="https://protomaps.com">Protomaps</a> © <a href="https://openstreetmap.org">OpenStreetMap</a>'
							}
						}
					: {};

				const basemapLayers: maplibregl.LayerSpecification[] = basemapUrl
					? (protomapsLayers(BASEMAP_SOURCE_ID, namedFlavor('light'), {
							lang: 'en'
						}) as maplibregl.LayerSpecification[])
					: [];

				const spriteUrl = basemapUrl
					? new URL(SPRITE_URL, window.location.origin).toString()
					: undefined;

				initialBounds = [
					[header.minLon, header.minLat],
					[header.maxLon, header.maxLat]
				];

				const newMap = new maplibregl.Map({
					container,
					attributionControl: false,
					style: {
						version: 8,
						glyphs: GLYPHS_URL,
						sprite: spriteUrl,
						sources: {
							...basemapSources,
							[SOURCE_ID]: {
								type: 'vector',
								url: `pmtiles://${tilesUrl}`
							}
						},
						layers: [
							...basemapLayers,
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
									'text-color': LABEL_INK,
									'text-halo-color': LABEL_HALO,
									'text-halo-width': 1.5
								}
							}
						]
					},
					bounds: initialBounds,
					fitBoundsOptions: { padding: 20 }
				});
				created = newMap;

				newMap.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');

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

	$effect(() => {
		if (map === null) return;

		if (marker === null || marker === undefined) {
			addressMarker?.remove();
			addressMarker = null;
			return;
		}

		if (addressMarker === null) {
			addressMarker = new maplibregl.Marker({ color: '#e02424' });
		}
		addressMarker.setLngLat([marker.lng, marker.lat]).addTo(map);
	});

	$effect(() => {
		if (map === null) return;

		const visibility = showBasemap ? 'visible' : 'none';
		for (const layer of map.getStyle().layers) {
			if ('source' in layer && layer.source === BASEMAP_SOURCE_ID) {
				map.setLayoutProperty(layer.id, 'visibility', visibility);
			}
		}
	});
</script>

<div class="relative h-[520px] w-full">
	<div bind:this={container} class="bg-surface-sunken h-full w-full rounded"></div>

	{#if map}
		<button
			type="button"
			onclick={recenter}
			class="border-line-default bg-surface-raised text-ink-secondary hover:bg-surface-sunken absolute top-3 right-3 cursor-pointer rounded border px-3 py-1.5 text-sm shadow-sm transition-colors"
		>
			Recenter
		</button>
	{/if}
</div>
