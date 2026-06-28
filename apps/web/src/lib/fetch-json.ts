/**
 * Shared helpers for fetching and parsing build artifacts.
 */

export async function fetchJson<T>(
	url: string,
	label: string,
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<T> {
	const response = await fetch(url);
	if (!response.ok) {
		throw new Error(
			`failed to fetch ${label} at ${url}: ${response.status} ${response.statusText}`
		);
	}
	return (await response.json()) as T;
}

export async function fetchVersionedJson<T extends { schema_version: number }>(
	url: string,
	label: string,
	expectedVersion: number,
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<T> {
	const data = await fetchJson<T>(url, label, fetch);
	if (data.schema_version !== expectedVersion) {
		throw new Error(
			`${label} schema_version ${data.schema_version} is not supported by this build`
		);
	}
	return data;
}
