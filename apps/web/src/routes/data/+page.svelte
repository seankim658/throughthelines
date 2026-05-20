<script lang="ts">
	import type { PageData } from './$types';
	import { getCoveredStateCodes, getPlannedStateCodes } from '$lib/copy/coverage';
	import { STATE_NAMES } from '$lib/states/states';

	let { data }: { data: PageData } = $props();

	const covered = $derived(getCoveredStateCodes(data.manifest));
	const planned = $derived(getPlannedStateCodes(data.manifest));
</script>

<svelte:head>
	<title>Data · Through the Lines</title>
</svelte:head>

{#snippet stateLink(code: string)}
	<a href="/{code.toLowerCase()}" class="decoration-accent underline underline-offset-4"
		>{STATE_NAMES[code]}</a
	>
{/snippet}

<div class="mx-auto max-w-3xl space-y-8 p-8">
	<h1 class="tracking-light font-serif text-5xl font-semibold">Data</h1>

	<p class="text-ink-secondary">
		Through the Lines is built incrementally. This page tracks what's available now and what's
		planned next.
	</p>

	<section class="space-y-2">
		<h2 class="text-2xl">Currently covered</h2>
		{#if covered.length > 0}
			<p>Through the Lines currently covers these states:</p>
			<ul class="list-none space-y-1 p-0">
				{#each covered as code (code)}
					<li>{@render stateLink(code)}</li>
				{/each}
			</ul>
		{:else}
			<p class="text-ink-muted">No states are covered yet.</p>
		{/if}
	</section>

	<section class="space-y-2">
		<h2 class="text-2xl">Planned</h2>
		{#if planned.length > 0}
			<p>These states are planned next:</p>
			<ul class="list-none space-y-1 p-0">
				{#each planned as code (code)}
					<li>{@render stateLink(code)}</li>
				{/each}
			</ul>
		{:else}
			<p class="text-ink-muted">No states are currently planned.</p>
		{/if}
	</section>
</div>
