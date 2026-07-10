<script lang="ts">
	import { tokenizeProse, citationAnchorId, type PlanCitations } from './citations';

	let {
		text,
		citations,
		planId
	}: {
		text: string;
		citations: PlanCitations;
		planId: string;
	} = $props();

	const segments = $derived(tokenizeProse(text, citations));
</script>

<!-- prettier-ignore -->
<p class="text-ink-secondary mt-2 text-sm whitespace-pre-line">{#each segments as segment, i (i)}{#if segment.kind === 'text'}{segment.text}{:else if segment.refKind === 'source'}<a href="#{citationAnchorId(planId, segment.code)}" class="text-accent align-super text-[0.7em] no-underline hover:underline" aria-label="Jump to reference {segment.code}">[{segment.number}]</a>{:else}<a href="#{citationAnchorId(planId, segment.code)}" class="text-accent align-super font-mono text-[0.7em] no-underline hover:underline" aria-label="Jump to reference {segment.code}">[{segment.code}]</a>{/if}{/each}</p>
