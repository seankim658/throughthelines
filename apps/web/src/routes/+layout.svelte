<script lang="ts">
	import '../app.css';
	import '@fontsource/inter/400.css';
	import '@fontsource/inter/500.css';
	import '@fontsource/inter/600.css';
	import '@fontsource/source-serif-4/600.css';
	import '@fontsource/source-serif-4/700.css';
	import '@fontsource/source-serif-4/400-italic.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';
	import SiteHeader from '$lib/ui/SiteHeader.svelte';
	import SiteFooter from '$lib/ui/SiteFooter.svelte';

	let { data, children } = $props();

	const isHome = $derived(page.route.id === '/');
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="flex min-h-dvh flex-col">
	{#if !isHome}
		<SiteHeader />
	{/if}

	<main class="flex-1">
		{@render children()}
	</main>

	<SiteFooter manifest={data.manifest} />
</div>
