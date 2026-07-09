<script lang="ts">
	import { tokenizeProse, citationAnchorId } from './citations';

	let {
		text,
		numbers,
		planId
	}: {
		text: string;
		numbers: Map<string, number>;
		planId: string;
	} = $props();

	const segments = $derived(tokenizeProse(text, numbers));
</script>

<!-- prettier-ignore -->
<p class="text-ink-secondary mt-2 text-sm whitespace-pre-line">{#each segments as segment}{#if segment.kind === 'text'}{segment.text}{:else}<a href="#{citationAnchorId(planId, segment.code)}" class="text-accent align-super text-[0.7em] no-underline hover:underline" aria-label="Jump to reference {segment.code}">[{segment.number}]</a>{/if}{/each}</p>
