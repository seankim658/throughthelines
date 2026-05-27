<script lang="ts">
	/**
	 * CrossDecadeChain: how a 2020 Census block is linked back through older
	 * block vintages.
	 */

	let { caption = '' }: { caption?: string } = $props();
</script>

<figure class="ttl-diagram">
	<svg
		viewBox="0 0 680 250"
		role="img"
		aria-labelledby="cdc-title cdc-desc"
		xmlns="http://www.w3.org/2000/svg"
	>
		<title id="cdc-title">Cross-decade block linkage</title>
		<desc id="cdc-desc">
			A 2020 Census block is linked to a 2010 block and then a 2000 block by testing which older
			block contains the newer block's interior point.
		</desc>

		<defs>
			<marker
				id="cdc-arrowhead"
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

		<!-- Arrows (drawn first so tiles/pills sit on top) -->
		<line
			x1="178"
			y1="105"
			x2="257"
			y2="105"
			class="ttl-diagram-arrow"
			marker-end="url(#cdc-arrowhead)"
		/>
		<line
			x1="423"
			y1="105"
			x2="502"
			y2="105"
			class="ttl-diagram-arrow"
			marker-end="url(#cdc-arrowhead)"
		/>

		<!-- Tile 1: 2020 blocks -->
		<rect x="20" y="30" width="150" height="150" rx="6" class="ttl-diagram-node" />
		<line x1="85" y1="30" x2="85" y2="180" class="ttl-diagram-gridline" />
		<line x1="20" y1="110" x2="170" y2="110" class="ttl-diagram-gridline" />
		<rect x="20" y="30" width="65" height="80" class="ttl-diagram-cell-active" />
		<circle cx="52" cy="70" r="4" class="ttl-diagram-point" />
		<text x="95" y="205" class="ttl-diagram-label">2020 blocks</text>

		<!-- Tile 2: 2010 blocks -->
		<rect x="265" y="30" width="150" height="150" rx="6" class="ttl-diagram-node" />
		<line x1="355" y1="30" x2="355" y2="180" class="ttl-diagram-gridline" />
		<line x1="265" y1="95" x2="415" y2="95" class="ttl-diagram-gridline" />
		<rect x="265" y="30" width="90" height="65" class="ttl-diagram-cell-active" />
		<circle cx="310" cy="62" r="4" class="ttl-diagram-point" />
		<text x="340" y="205" class="ttl-diagram-label">2010 blocks</text>

		<!-- Tile 3: 2000 blocks -->
		<rect x="510" y="30" width="150" height="150" rx="6" class="ttl-diagram-node" />
		<line x1="575" y1="30" x2="575" y2="180" class="ttl-diagram-gridline" />
		<line x1="510" y1="120" x2="660" y2="120" class="ttl-diagram-gridline" />
		<rect x="510" y="30" width="65" height="90" class="ttl-diagram-cell-active" />
		<circle cx="542" cy="75" r="4" class="ttl-diagram-point" />
		<text x="585" y="205" class="ttl-diagram-label">2000 blocks</text>

		<!-- Pills on the arrows (fill matches panel to mask the line) -->
		<rect x="175.5" y="94" width="84" height="22" rx="11" class="ttl-diagram-pill" />
		<text x="217.5" y="105" class="ttl-diagram-pill-text">falls inside</text>

		<rect x="420.5" y="94" width="84" height="22" rx="11" class="ttl-diagram-pill" />
		<text x="462.5" y="105" class="ttl-diagram-pill-text">falls inside</text>

		<!-- Takeaway -->
		<text x="340" y="232" class="ttl-diagram-caption">
			A block's interior point selects the block that contains it in the older vintage.
		</text>
	</svg>

	{#if caption}
		<figcaption>{caption}</figcaption>
	{/if}
</figure>
