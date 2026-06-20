<script lang="ts">
	import { onMount } from 'svelte';
	import { getStoredPreference, setPreference, type ThemePreference } from '$lib/theme/theme';

	let preference = $state<ThemePreference>('system');

	onMount(() => {
		preference = getStoredPreference();
	});

	function choose(next: ThemePreference): void {
		preference = next;
		setPreference(next);
	}

	type Option = {
		value: ThemePreference;
		label: string;
	};

	const options: Option[] = [
		{ value: 'light', label: 'Light theme' },
		{ value: 'dark', label: 'Dark theme' },
		{ value: 'system', label: 'System theme' }
	];
</script>

<div
	role="group"
	aria-label="Theme preference"
	class="border-line-default bg-surface-raised inline-flex rounded-full border p-0.5"
>
	{#each options as opt (opt.value)}
		<button
			type="button"
			aria-label={opt.label}
			aria-pressed={preference === opt.value}
			onclick={() => choose(opt.value)}
			class="text-ink-muted hover:text-ink-primary aria-pressed:bg-surface-sunken aria-pressed:text-ink-primary flex h-7 w-7 cursor-pointer items-center justify-center rounded-full transition-colors"
		>
			{#if opt.value === 'light'}
				<!-- Sun -->
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					class="h-4 w-4"
					aria-hidden="true"
				>
					<circle cx="12" cy="12" r="4" />
					<path d="M12 2v2" />
					<path d="M12 20v2" />
					<path d="m4.93 4.93 1.41 1.41" />
					<path d="m17.66 17.66 1.41 1.41" />
					<path d="M2 12h2" />
					<path d="M20 12h2" />
					<path d="m6.34 17.66-1.41 1.41" />
					<path d="m19.07 4.93-1.41 1.41" />
				</svg>
			{:else if opt.value === 'dark'}
				<!-- Moon -->
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					class="h-4 w-4"
					aria-hidden="true"
				>
					<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
				</svg>
			{:else}
				<!-- Monitor -->
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					stroke-linecap="round"
					stroke-linejoin="round"
					class="h-4 w-4"
					aria-hidden="true"
				>
					<rect width="20" height="14" x="2" y="3" rx="2" />
					<line x1="8" x2="16" y1="21" y2="21" />
					<line x1="12" x2="12" y1="17" y2="21" />
				</svg>
			{/if}
		</button>
	{/each}
</div>
