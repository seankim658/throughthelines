<script lang="ts">
	import { NC12_PATH, NC12_VIEWBOX } from './nc12-path';

	const viewBox = `${NC12_VIEWBOX.minX} ${NC12_VIEWBOX.minY} ${NC12_VIEWBOX.width} ${NC12_VIEWBOX.height}`;
</script>

<svg
	{viewBox}
	xmlns="http://www.w3.org/2000/svg"
	preserveAspectRatio="xMidYMid slice"
	aria-hidden="true"
	class="block h-full w-full"
>
	<path d={NC12_PATH} class="shape" />
</svg>

<style>
	svg {
		transform: scale(1.35);
		transform-origin: 60% 50%;
	}

	.shape {
		fill: var(--color-accent);
		fill-opacity: 0.1;
		stroke: var(--color-accent);
		stroke-width: 1;
		stroke-opacity: 0.45;
		stroke-linejoin: round;
		vector-effect: non-scaling-stroke;
	}
</style>

