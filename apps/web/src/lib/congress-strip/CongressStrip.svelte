<script lang="ts">
	import type { CongressEntry } from '$lib/manifest/types';
	import { formatCongressYears } from '$lib/congress/congress-years';

	let {
		congresses,
		activeCongress = $bindable(),
		districts = null
	}: {
		congresses: CongressEntry[];
		activeCongress: number;
		/**
		 * Per-Congress district assignment for a matched address.
		 * - null: no lookup is ready (idle, in-progress, or terminal error).
		 *   Cells render an em-dash placeholder in the district slot.
		 * - Record: lookup is ready. Values are district numbers, or null
		 *   when the block had no district assignment for that Congress.
		 */
		districts?: Record<number, number | null> | null;
	} = $props();

	// Newest Congress at the top, oldest at the bottom.
	const ordered = $derived([...congresses].reverse());

	function districtLabel(congress: number): string {
		if (districts === null) return '—';
		const d = districts[congress];
		if (d === null || d === undefined) return '—';
		return `District ${d}`;
	}
</script>

<ul class="flex list-none flex-col p-0">
	{#each ordered as entry (entry.congress)}
		<li>
			<button
				type="button"
				class="group text-ink-primary hover:bg-surface-sunken aria-pressed:bg-accent aria-pressed:text-accent-ink w-full cursor-pointer rounded px-3 py-2 text-left transition-colors"
				aria-pressed={entry.congress === activeCongress}
				onclick={() => (activeCongress = entry.congress)}
			>
				<div class="text-ink-muted group-aria-pressed:text-accent-ink text-xs">
					{entry.congress}th · {formatCongressYears(entry.congress)}
				</div>
				<div class="text-base font-medium">{districtLabel(entry.congress)}</div>
			</button>
		</li>
	{/each}
</ul>
