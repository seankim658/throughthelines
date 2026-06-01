<script lang="ts">
	/**
	 * BuildPipeline, the build-time data flow.
	 *
	 * Five independent steps, each turning pinned upstream sources into one
	 * artifact; the manifest is built last and references all of them.
	 */

	let { caption = '' }: { caption?: string } = $props();

	interface Lane {
		readonly source: string;
		readonly sourceExtra?: string;
		readonly step: string;
		readonly artifact: string;
		readonly scope: 'shared' | 'per state';
	}

	// --- Layout constants ---
	const VIEW_W = 720;
	const VIEW_H = 384;

	const SOURCE_X = 14;
	const SOURCE_W = 176;
	const SOURCE_CX = SOURCE_X + SOURCE_W / 2;
	const SOURCE_RIGHT = SOURCE_X + SOURCE_W;

	const ART_X = 366;
	const ART_W = 176;
	const ART_CX = ART_X + ART_W / 2;
	const ART_RIGHT = ART_X + ART_W;

	const STEP_CX = (SOURCE_RIGHT + ART_X) / 2;
	const PILL_W = 120;
	const PILL_H = 22;

	const MANI_X = 580;
	const MANI_W = 126;
	const MANI_CX = MANI_X + MANI_W / 2;

	const NODE_H = 46;
	const LANE_H = 60;
	const FIRST_CY = 80;

	const GAP = 6;

	const rawLanes: readonly Lane[] = [
		{ source: 'Plan YAMLs', step: 'validate', artifact: 'plan_index.json', scope: 'shared' },
		{
			source: 'Plan YAMLs',
			sourceExtra: '+ Lewis polygons',
			step: 'stitch → tiles',
			artifact: '{state}.pmtiles',
			scope: 'per state'
		},
		{
			source: 'Census blocks + BEFs',
			sourceExtra: '+ Lewis polygons',
			step: 'blocks',
			artifact: 'block_lookup.json',
			scope: 'per state'
		},
		{ source: 'Voteview', step: 'members', artifact: 'members.json', scope: 'shared' },
		{ source: 'Protomaps', step: 'basemap', artifact: 'basemap.pmtiles', scope: 'shared' }
	];

	const lanes = rawLanes.map((lane, i) => ({ ...lane, cy: FIRST_CY + i * LANE_H }));

	const maniY = FIRST_CY - NODE_H / 2;
	const maniH = lanes[lanes.length - 1].cy + NODE_H / 2 - maniY;
	const maniMidY = maniY + maniH / 2;
</script>

<figure class="ttl-diagram">
	<svg
		viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
		role="img"
		aria-labelledby="bp-title bp-desc"
		xmlns="http://www.w3.org/2000/svg"
	>
		<title id="bp-title">The build pipeline</title>
		<desc id="bp-desc">
			Each pipeline step turns pinned upstream sources into one published artifact: plan YAMLs
			become the plan index, plan YAMLs and polygons become map tiles, Census data becomes the block
			lookup, Voteview becomes the members file, and Protomaps becomes the basemap. The manifest is
			built last and references every artifact.
		</desc>

		<defs>
			<marker
				id="bp-arrowhead"
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

		<!-- Column headers -->
		<text x={SOURCE_CX} y="28" class="ttl-diagram-sublabel">SOURCES</text>
		<text x={STEP_CX} y="28" class="ttl-diagram-sublabel">STEP</text>
		<text x={ART_CX} y="28" class="ttl-diagram-sublabel">ARTIFACTS</text>
		<text x={MANI_CX} y="28" class="ttl-diagram-sublabel">MANIFEST</text>

		<!-- Manifest node -->
		<rect
			x={MANI_X}
			y={maniY}
			width={MANI_W}
			height={maniH}
			rx="8"
			class="ttl-diagram-node ttl-diagram-node-out"
		/>
		<text x={MANI_CX} y={maniMidY - 18} class="ttl-diagram-label ttl-diagram-label-out">
			manifest.json
		</text>
		<text x={MANI_CX} y={maniMidY + 2} class="ttl-diagram-sublabel">references all,</text>
		<text x={MANI_CX} y={maniMidY + 20} class="ttl-diagram-sublabel">built last</text>

		<!-- Lanes -->
		{#each lanes as lane (lane.step)}
			<!-- Arrows -->
			<line
				x1={SOURCE_RIGHT + GAP}
				y1={lane.cy}
				x2={ART_X - GAP}
				y2={lane.cy}
				class="ttl-diagram-arrow"
				marker-end="url(#bp-arrowhead)"
			/>
			<line
				x1={ART_RIGHT + GAP}
				y1={lane.cy}
				x2={MANI_X - GAP}
				y2={lane.cy}
				class="ttl-diagram-arrow"
				marker-end="url(#bp-arrowhead)"
			/>

			<!-- Source node -->
			<rect
				x={SOURCE_X}
				y={lane.cy - NODE_H / 2}
				width={SOURCE_W}
				height={NODE_H}
				rx="8"
				class="ttl-diagram-node"
			/>
			{#if lane.sourceExtra}
				<text x={SOURCE_CX} y={lane.cy - 8} class="ttl-diagram-label">{lane.source}</text>
				<text x={SOURCE_CX} y={lane.cy + 9} class="ttl-diagram-sublabel">{lane.sourceExtra}</text>
			{:else}
				<text x={SOURCE_CX} y={lane.cy} class="ttl-diagram-label">{lane.source}</text>
			{/if}

			<!-- Artifact node -->
			<rect
				x={ART_X}
				y={lane.cy - NODE_H / 2}
				width={ART_W}
				height={NODE_H}
				rx="8"
				class="ttl-diagram-node"
			/>
			<text x={ART_CX} y={lane.cy - 8} class="ttl-diagram-label">{lane.artifact}</text>
			<text x={ART_CX} y={lane.cy + 9} class="ttl-diagram-sublabel">{lane.scope}</text>

			<!-- Step pill -->
			<rect
				x={STEP_CX - PILL_W / 2}
				y={lane.cy - PILL_H / 2}
				width={PILL_W}
				height={PILL_H}
				rx={PILL_H / 2}
				class="ttl-diagram-pill"
			/>
			<text x={STEP_CX} y={lane.cy} class="ttl-diagram-pill-text">{lane.step}</text>
		{/each}

		<!-- Takeaway -->
		<text x={VIEW_W / 2} y={VIEW_H - 18} class="ttl-diagram-caption">
			Everything is computed at build time; the browser reads the manifest first, then the files it
			points to.
		</text>
	</svg>

	{#if caption}
		<figcaption>{caption}</figcaption>
	{/if}
</figure>
