<script lang="ts">
	import ThemeToggle from './ThemeToggle.svelte';
</script>

<header class="border-line-subtle bg-surface-page/85 sticky top-0 z-30 border-b backdrop-blur-sm">
	<div class="mx-auto flex max-w-6xl items-center justify-between px-8 py-1.5">
		<a href="/" class="text-ink-primary hover:text-accent font-serif text-xl">
			Through the Lines
		</a>
		<ThemeToggle />
	</div>
</header>
