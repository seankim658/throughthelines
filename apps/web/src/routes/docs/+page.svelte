<script lang="ts">
	import { DOC_GROUP_ORDER, pagesInGroup } from '$lib/docs/nav';
</script>

<div class="space-y-8">
	<h1 class="font-serif text-5xl font-semibold tracking-tight">Documentation</h1>

	<p class="text-ink-secondary">
		Everything about Through the Lines. What it does, how the address lookup works, the data model
		behind it, and how to contribute.
	</p>

	{#each DOC_GROUP_ORDER as group (group)}
		<section class="space-y-4">
			<h2 class="text-2xl">{group}</h2>
			<ul class="list-none space-y-4 p-0">
				{#each pagesInGroup(group) as doc (doc.slug)}
					<li>
						<a href={`/docs/${doc.slug}`} class="text-accent underline underline-offset-4">
							{doc.title}
						</a>
						<p class="text-ink-secondary mt-1">{doc.description}</p>
					</li>
				{/each}
			</ul>
		</section>
	{/each}
</div>
