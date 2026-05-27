<script lang="ts">
	import ThemeToggle from './ThemeToggle.svelte';

	const links = [
		{ href: '/data', label: 'Data' },
		{ href: '/docs', label: 'Docs' }
	];
</script>

<header class="border-line-subtle bg-surface-page/85 sticky top-0 z-30 border-b backdrop-blur-sm">
	<div class="mx-auto flex max-w-6xl items-center justify-between px-8 py-1.5">
		<a href="/" class="text-ink-primary hover:text-accent font-serif text-xl">
			Through the Lines
		</a>
		<div class="flex items-center gap-6">
			<nav class="flex items-center gap-5 text-sm" aria-label="Primary">
				{#each links as link (link.href)}
					<a href={link.href} class="text-ink-secondary hover:text-accent transition-colors">
						{link.label}
					</a>
				{/each}
			</nav>
			<ThemeToggle />
		</div>
	</div>
</header>
