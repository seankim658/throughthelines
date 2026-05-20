<script lang="ts">
	import type { PageData } from './$types';
	import { getCoveredStateCodes, getPlannedStateCodes, joinWithAnd } from '$lib/copy/coverage';
	import { STATE_NAMES } from '$lib/states/states';
	import UsMapWatermark from '$lib/states/UsMapWatermark.svelte';
	import ThemeToggle from '$lib/ui/ThemeToggle.svelte';

	let { data }: { data: PageData } = $props();

	const coveredCodes = $derived(getCoveredStateCodes(data.manifest));
	const plannedCodes = $derived(getPlannedStateCodes(data.manifest));
</script>

<svelte:head>
	<title>Through the Lines</title>
</svelte:head>

{#snippet stateLink(code: string)}
	<a href="/{code.toLowerCase()}" class="decoration-accent underline underline-offset-4">
		{STATE_NAMES[code]}
	</a>
{/snippet}

<div class="absolute top-4 right-6 z-20">
	<ThemeToggle />
</div>

<section class="relative flex min-h-screen flex-col justify-center px-12 pt-32 pb-40 md:px-20">
	<!-- Watermark: full-width, vertically anchored to the section, behind content. -->
	<div
		class="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center overflow-hidden"
	>
		<UsMapWatermark manifest={data.manifest} />
	</div>

	<div class="mx-auto w-full max-w-5xl">
		<h1 class="font-serif text-6xl leading-[0.95] font-semibold tracking-tight lg:text-7xl">
			Through the Lines
		</h1>

		<p class="text-ink-primary mt-12 max-w-2xl font-serif text-2xl leading-snug italic">
			Every U.S. congressional district your address has lived under, with the plan that drew each
			one and the rulings that reshaped them.
		</p>

		<p class="text-ink-secondary mt-6 max-w-2xl">
			An open dataset and lookup tool. Currently covering
			{#each coveredCodes as code, i (code)}{@render stateLink(
					code
				)}{#if i < coveredCodes.length - 1}{coveredCodes.length === 2
						? ' and '
						: i === coveredCodes.length - 2
							? ', and '
							: ', '}{/if}{/each}{#if plannedCodes.length > 0}. {joinWithAnd(
					plannedCodes.map((code) => STATE_NAMES[code])
				)}
				{plannedCodes.length === 1 ? 'is' : 'are'} planned next{/if}.
		</p>
	</div>
</section>

