<script lang="ts">
	import { getVersionLabel } from '$lib/copy/coverage';
	import type { Manifest } from '$lib/manifest/types';

	let { manifest }: { manifest: Manifest } = $props();

	const versionLabel = $derived(getVersionLabel(manifest));
	const builtDate = $derived(manifest.build.built_at.slice(0, 10));
	const shortSha = $derived(manifest.build.git_sha?.slice(0, 7) ?? 'unknown');
</script>

<footer class="border-line-subtle border-t">
	<div class="mx-auto max-w-6xl px-12 pr-16 py-6">
		<div class="flex flex-col items-baseline gap-8 md:flex-row md:justify-between">
			<!-- Identity -->
			<div class="md:max-w-sm">
				<a href="/" class="text-ink-primary hover:text-accent font-serif text-lg">
					Through the Lines
				</a>
				<p class="text-ink-muted mt-1 text-sm">
					How your congressional district was drawn... and redrawn.
				</p>
			</div>

			<div class="flex gap-14">
				<div>
					<h2 class="text-ink-muted text-xs font-medium tracking-wider uppercase">Project</h2>
					<ul class="mt-3 space-y-1.5 text-sm">
						<li>
							<a href="/data" class="text-ink-secondary hover:text-accent">Data</a>
						</li>
						<li>
							<a href="/docs" class="text-ink-secondary hover:text-accent">Docs</a>
						</li>
					</ul>
				</div>
				<div>
					<h2 class="text-ink-muted text-xs font-medium tracking-wider uppercase">Source</h2>
					<ul class="mt-3 space-y-1.5 text-sm">
						<li>
							<a
								href="https://github.com/seankim658/throughthelines"
								target="_blank"
								rel="noopener noreferrer"
								class="text-ink-secondary hover:text-accent"
							>
								GitHub
							</a>
						</li>
					</ul>
				</div>
				<div>
					<h2 class="text-ink-muted text-xs font-medium tracking-wider uppercase">Connect</h2>
					<ul class="mt-3 space-y-1.5 text-sm">
						<li>
							<a
								href="https://github.com/seankim658/throughthelines/issues"
								target="_blank"
								rel="noopener noreferrer"
								class="text-ink-secondary hover:text-accent"
							>
								Issues
							</a>
						</li>
						<li>
							<a href="/contact" class="text-ink-secondary hover:text-accent">Contact us</a>
						</li>
					</ul>
				</div>
			</div>
		</div>

		<div
			class="text-ink-muted mt-6 flex flex-col gap-2 text-xs sm:flex-row sm:items-center sm:justify-between"
		>
			<div>Code MIT <span aria-hidden="true">·</span> Data CC-BY 4.0</div>
			<div>
				<span>{versionLabel}</span>
				<span aria-hidden="true" class="mx-1.5">·</span>
				<span>built {builtDate}</span>
				<span aria-hidden="true" class="mx-1.5">·</span>
				<span class="font-mono">{shortSha}</span>
			</div>
		</div>
	</div>
</footer>
