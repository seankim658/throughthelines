<script lang="ts">
	/**
	 * "On this page" table of contents navigation.
	 *
	 * Scans the rendered content element for h2/h3 headings (which rehype-slug
	 * has already given ids) and builds a list of in-page anchors. A single
	 * IntersectionObserver highlights the heading nearest the top during scrolling.
	 */
	import { untrack } from 'svelte';

	interface TocEntry {
		readonly id: string;
		readonly text: string;
		readonly level: number;
	}

	let {
		contentEl,
		slug
	}: {
		contentEl: HTMLElement | null;
		slug: string;
	} = $props();

	let entries = $state<TocEntry[]>([]);
	let activeId = $state('');

	// Scan the DOM for headings
	$effect(() => {
		void slug; // re-scan on page change
		const el = contentEl;
		if (el === null) {
			untrack(() => (entries = []));
			return;
		}

		const found = Array.from(el.querySelectorAll<HTMLElement>('h2, h3'))
			.filter((h) => h.id !== '')
			.map((h) => ({
				id: h.id,
				text: h.textContent ?? '',
				level: Number(h.tagName.slice(1))
			}));

		untrack(() => (entries = found));
	});

	// Scroll spy
	$effect(() => {
		if (entries.length === 0) {
			untrack(() => (activeId = ''));
			return;
		}

		const observer = new IntersectionObserver(
			(observed) => {
				for (const entry of observed) {
					if (entry.isIntersecting) {
						activeId = entry.target.id;
					}
				}
			},
			{ rootMargin: '0px 0px -80% 0px' }
		);

		for (const entry of entries) {
			const el = document.getElementById(entry.id);
			if (el !== null) observer.observe(el);
		}

		return () => observer.disconnect();
	});
</script>

{#if entries.length > 0}
	<nav aria-label="On this page" class="text-sm">
		<h2 class="text-ink-muted mb-2 text-xs font-medium tracking-wider uppercase">On this page</h2>
		<ul class="space-y-1.5">
			{#each entries as entry (entry.id)}
				<li class={entry.level === 3 ? 'pl-3' : ''}>
					<a
						href={`#${entry.id}`}
						aria-current={activeId === entry.id ? 'true' : undefined}
						class={`block transition-colors ${
							activeId === entry.id ? 'text-accent' : 'text-ink-muted hover:text-ink-primary'
						}`}
					>
						{entry.text}
					</a>
				</li>
			{/each}
		</ul>
	</nav>
{/if}
