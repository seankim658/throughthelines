<script lang="ts">
	import type { PageData } from './$types';
	import { getCoveredStateCodes, getPlannedStateCodes } from '$lib/copy/coverage';
	import { STATE_NAMES } from '$lib/states/states';
	import {
		DATA_SOURCES,
		resolveSourceUrl,
		formatAccessDate,
		type DataSource
	} from '$lib/copy/sources';

	let { data }: { data: PageData } = $props();

	const covered = $derived(getCoveredStateCodes(data.manifest));
	const planned = $derived(getPlannedStateCodes(data.manifest));
	const accessDate = $derived(formatAccessDate(data.manifest));
</script>

<svelte:head>
	<title>Data · Through the Lines</title>
</svelte:head>

{#snippet stateLink(code: string)}
	<a href="/{code.toLowerCase()}" class="decoration-accent underline underline-offset-4"
		>{STATE_NAMES[code]}</a
	>
{/snippet}

{#snippet sourceItem(source: DataSource)}
	<li>
		<a
			href={resolveSourceUrl(data.manifest, source.link)}
			target="_blank"
			rel="noopener noreferrer"
			class="text-accent underline underline-offset-4"
		>
			{source.name}
		</a>
		<p class="text-ink-muted mt-1 text-sm">
			{source.license}{#if source.note}
				· {source.note}{/if}
		</p>
		<p class="text-ink-secondary pb-2">{source.description}</p>
		{#if source.citation}
			<div>
				<span class="text-ink-muted text-xs font-medium tracking-wider uppercase">Citation</span>
				<p class="text-ink-secondary mt-1 text-sm leading-relaxed">
					{#each source.citation as segment, i (i)}
						{#if segment.type === 'italic'}<em>{segment.value}</em
							>{:else if segment.type === 'access_date'}{accessDate}{:else}{segment.value}{/if}
					{/each}
				</p>
			</div>
		{/if}
	</li>
{/snippet}

<div class="mx-auto max-w-3xl space-y-8 p-8">
	<h1 class="tracking-light font-serif text-5xl font-semibold">Data</h1>

	<p class="text-ink-secondary">
		Through the Lines is built incrementally. This page tracks what's available now, what's planned
		next, and where the data comes from.
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

	<section class="space-y-6 pb-8">
		<h2 class="text-2xl">Data sources</h2>
		<p class="text-ink-secondary">
			Through the Lines stitches together several open datasets and reference sources:
		</p>
		<ul class="list-none space-y-4 p-0">
			{#each DATA_SOURCES as source (source.name)}
				{@render sourceItem(source)}
			{/each}
		</ul>
		<p class="text-ink-secondary pt-2">
			For how these fit together, the full address-to-district lookup chain, and the data model see
			the
			<a href="/docs" class="decoration-accent underline underline-offset-4">documentation</a>.
		</p>
	</section>
</div>
