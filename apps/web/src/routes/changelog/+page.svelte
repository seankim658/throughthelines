<script lang="ts">
	import { CHANGELOG, formatEntryDate } from '$lib/copy/changelog';
</script>

<svelte:head>
	<title>Changelog · Through the Lines</title>
</svelte:head>

<div class="mx-auto max-w-3xl space-y-8 p-8">
	<h1 class="tracking-light font-serif text-5xl font-semibold">Changelog</h1>

	<p class="text-ink-secondary">Notable changes to Through the Lines, newest first.</p>

	<ul class="list-none space-y-8 p-0">
		{#each CHANGELOG as entry (entry.version)}
			<li class="space-y-2">
				<div class="flex items-baseline gap-3">
					<h2 class="text-2xl">{entry.version}</h2>
					<span class="text-ink-muted text-sm">{formatEntryDate(entry.date)}</span>
				</div>
				<ul class="text-ink-secondary list-disc space-y-1 pl-5">
					{#each entry.changes as change, i (i)}
						<li>{change}</li>
					{/each}
				</ul>
			</li>
		{/each}
	</ul>
</div>
