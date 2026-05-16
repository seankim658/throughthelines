<script lang="ts">
	let {
		disabled,
		placeholder,
		onSubmit,
		onClear
	}: {
		disabled: boolean;
		placeholder: string;
		onSubmit: (address: string) => void;
		onClear: () => void;
	} = $props();

	let address = $state('');

	function handleSubmit(event: SubmitEvent): void {
		event.preventDefault();
		const trimmed = address.trim();
		if (trimmed.length === 0) return;
		onSubmit(trimmed);
	}

	function handleClear(): void {
		address = '';
		onClear();
	}
</script>

<form onsubmit={handleSubmit} class="flex items-end gap-3">
	<label class="text-ink-secondary flex flex-col text-sm">
		Address
		<input
			type="text"
			bind:value={address}
			{placeholder}
			{disabled}
			autocomplete="street-address"
			class="border-line-default bg-surface-raised text-ink-primary mt-1 w-96 rounded border px-3 py-2"
		/>
	</label>
	<button
		type="submit"
		{disabled}
		class="bg-accent text-accent-ink hover:bg-accent-hover active:bg-accent-active cursor-pointer rounded px-4 py-1.75 disabled:opacity-50"
	>
		Look up
	</button>
	<button
		type="button"
		disabled={disabled || address.length === 0}
		onclick={handleClear}
		class="border-line-default text-ink-secondary hover:bg-surface-sunken cursor-pointer rounded border px-4 py-1.75 transition-colors disabled:opacity-50"
	>
		Clear
	</button>
</form>
