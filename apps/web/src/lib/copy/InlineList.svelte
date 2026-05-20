<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';

	let {
		items,
		item
	}: {
		items: readonly T[];
		item: Snippet<[T]>;
	} = $props();
</script>

{#each items as it, i}{@render item(it)}{#if i < items.length - 1}{#if items.length === 2}
			and
		{:else if i === items.length - 2}, and
		{:else},
		{/if}{/if}{/each}
