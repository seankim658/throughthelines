<script lang="ts">
	/**
	 * LookupChain — the runtime address-to-district lookup flow.
	 *
	 * Theme-aware with zero JS: every color is a CSS variable from app.css
	 * (via the .ttl-diagram* classes in prose.css), so the diagram recolors
	 * automatically when data-theme="dark" is set on <html>.
	 *
	 * Mirrors routes/[state]/+page.svelte (handleSubmit):
	 *   address --geocode()--> 2020 block GEOID --block_lookup--> timeline
	 */

	let { caption = '' }: { caption?: string } = $props();
</script>

<figure class="ttl-diagram">
	<svg
		viewBox="0 0 800 168"
		role="img"
		aria-labelledby="lc-title lc-desc"
		xmlns="http://www.w3.org/2000/svg"
	>
		<title id="lc-title">Address lookup flow</title>
		<desc id="lc-desc">
			An address is geocoded in the browser to a 2020 Census block, then looked up in block_lookup
			to produce a per-Congress district history.
		</desc>

		<defs>
			<marker
				id="lc-arrowhead"
				viewBox="0 0 10 10"
				refX="9"
				refY="5"
				markerWidth="7"
				markerHeight="7"
				orient="auto-start-reverse"
			>
				<path d="M0,0 L10,5 L0,10 z" class="ttl-diagram-arrowhead" />
			</marker>
		</defs>

		<!-- Arrows (drawn first so boxes/pills sit on top) -->
		<line
			x1="186"
			y1="60"
			x2="316"
			y2="60"
			class="ttl-diagram-arrow"
			marker-end="url(#lc-arrowhead)"
		/>
		<line
			x1="484"
			y1="60"
			x2="614"
			y2="60"
			class="ttl-diagram-arrow"
			marker-end="url(#lc-arrowhead)"
		/>

		<!-- Box A: input -->
		<rect x="24" y="28" width="156" height="64" rx="8" class="ttl-diagram-node" />
		<text x="102" y="53" class="ttl-diagram-label">Your address</text>
		<text x="102" y="72" class="ttl-diagram-sublabel">123 Main St</text>

		<!-- Box B: intermediate -->
		<rect x="322" y="28" width="156" height="64" rx="8" class="ttl-diagram-node" />
		<text x="400" y="53" class="ttl-diagram-label">2020 block</text>
		<text x="400" y="72" class="ttl-diagram-sublabel">15-digit GEOID</text>

		<!-- Box C: output (accented) -->
		<rect
			x="620"
			y="28"
			width="156"
			height="64"
			rx="8"
			class="ttl-diagram-node ttl-diagram-node-out"
		/>
		<text x="698" y="53" class="ttl-diagram-label ttl-diagram-label-out">District history</text>
		<text x="698" y="72" class="ttl-diagram-sublabel">2001–present</text>

		<!-- Pills on the arrows (fill matches panel to mask the line) -->
		<rect x="195" y="49" width="112" height="22" rx="11" class="ttl-diagram-pill" />
		<text x="251" y="60" class="ttl-diagram-pill-text">Census Geocoder</text>

		<rect x="493" y="49" width="112" height="22" rx="11" class="ttl-diagram-pill" />
		<text x="549" y="60" class="ttl-diagram-pill-code">block_lookup</text>

		<!-- Footer: the privacy point -->
		<text x="400" y="146" class="ttl-diagram-caption">
			Your address goes directly to the U.S. Census Bureau Geocoding API, never to Through the
			Lines.
		</text>
	</svg>

	{#if caption}
		<figcaption>{caption}</figcaption>
	{/if}
</figure>
