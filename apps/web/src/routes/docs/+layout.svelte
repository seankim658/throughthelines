<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import {
		DOC_GROUP_ORDER,
		pagesInGroup,
		neighborsOf,
		findDocPage,
		formatLastUpdated
	} from '$lib/docs/nav';
	import TableOfContents from '$lib/docs/TableOfContents.svelte';
	import '$lib/docs/prose.css';

	let { children }: { children: Snippet } = $props();

	let contentEl = $state<HTMLElement | null>(null);

	const DOCS_PREFIX = '/docs';

	const currentSlug = $derived.by(() => {
		const path = page.url.pathname.replace(/\/+$/, '');
		if (path === DOCS_PREFIX) return '';
		return path.startsWith(`${DOCS_PREFIX}/`) ? path.slice(DOCS_PREFIX.length + 1) : '';
	});

	const currentPage = $derived(findDocPage(currentSlug));
	const neighbors = $derived(neighborsOf(currentSlug));
	const docTitle = $derived(
		currentPage
			? `${currentPage.title} · Docs · Through the Lines`
			: 'Documentation · Through the Lines'
	);
	const docDescription = $derived(
		currentPage?.description ?? 'Documentation for Through the Lines'
	);
</script>

<svelte:head>
	<title>{docTitle}</title>
	<meta name="description" content={docDescription} />
</svelte:head>

{#snippet sidebarNav()}
	<nav aria-label="Documentation">
		<a
			href={DOCS_PREFIX}
			aria-current={currentSlug === '' ? 'page' : undefined}
			class={`mb-6 block text-sm transition-colors ${
				currentSlug === '' ? 'text-accent font-medium' : 'text-ink-secondary hover:text-ink-primary'
			}`}
		>
			Documentation home
		</a>
		{#each DOC_GROUP_ORDER as group (group)}
			<div class="mb-6">
				<h2 class="text-ink-muted mb-2 text-xs font-medium tracking-wider uppercase">
					{group}
				</h2>
				<ul class="space-y-0.5">
					{#each pagesInGroup(group) as doc (doc.slug)}
						<li>
							<a
								href={`${DOCS_PREFIX}/${doc.slug}`}
								aria-current={currentSlug === doc.slug ? 'page' : undefined}
								class={`block border-l-2 py-1 pl-3 text-sm transition-colors ${
									currentSlug === doc.slug
										? 'border-accent text-accent font-medium'
										: 'text-ink-secondary hover:text-ink-primary border-transparent'
								}`}
							>
								{doc.title}
							</a>
						</li>
					{/each}
				</ul>
			</div>
		{/each}
	</nav>
{/snippet}

<div class="mx-auto w-full max-w-3xl px-6 py-10 lg:max-w-5xl xl:max-w-7xl">
	<div
		class="lg:grid lg:grid-cols-[15rem_minmax(0,1fr)] lg:items-start lg:gap-12 xl:grid-cols-[15rem_minmax(0,1fr)_13rem]"
	>
		<!-- Mobile: collapsible menu -->
		<details
			class="border-line-subtle bg-surface-sunken mb-6 rounded-lg border px-4 py-2 lg:hidden"
		>
			<summary class="text-ink-primary cursor-pointer text-sm font-medium">
				Documentation menu
			</summary>
			<div class="mt-4">
				{@render sidebarNav()}
			</div>
		</details>

		<aside class="hidden lg:sticky lg:top-20 lg:block">
			{@render sidebarNav()}
		</aside>

		<div class="relative min-w-0">
			{#if currentPage?.lastUpdated}
				<p class="text-ink-muted mb-2 text-right text-xs lg:absolute lg:top-4 lg:right-0 lg:mb-0">
					Last updated {formatLastUpdated(currentPage.lastUpdated)}
				</p>
			{/if}
			<div class="max-w-[70ch]" class:docs-prose={!!currentPage} bind:this={contentEl}>
				{@render children()}
			</div>

			{#if currentPage}
				<nav
					class="border-line-subtle mt-16 flex justify-between gap-4 border-t pt-6 text-sm"
					aria-label="Pagination"
				>
					{#if neighbors.previous}
						<a
							href={`${DOCS_PREFIX}/${neighbors.previous.slug}`}
							class="text-ink-secondary hover:text-ink-primary flex max-w-[15rem] flex-col"
						>
							<span class="text-ink-muted text-xs tracking-wider uppercase">Previous</span>
							<span class="text-ink-primary mt-0.5 font-medium">{neighbors.previous.title}</span>
						</a>
					{:else}
						<span></span>
					{/if}
					{#if neighbors.next}
						<a
							href={`${DOCS_PREFIX}/${neighbors.next.slug}`}
							class="text-ink-secondary hover:text-ink-primary flex max-w-[15rem] flex-col text-right"
						>
							<span class="text-ink-muted text-xs tracking-wider uppercase">Next</span>
							<span class="text-ink-primary mt-0.5 font-medium">{neighbors.next.title}</span>
						</a>
					{/if}
				</nav>
			{/if}
		</div>
		<aside class="hidden xl:sticky xl:top-20 xl:block">
			{#if currentPage}
				<TableOfContents {contentEl} slug={currentSlug} />
			{/if}
		</aside>
	</div>
</div>
