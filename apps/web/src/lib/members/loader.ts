import { resolveArtifactUrl } from '$lib/manifest/loader';
import type { Manifest } from '$lib/manifest/types';
import type { MembersIndex } from './types';

export async function loadMembers(
	manifest: Manifest,
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<MembersIndex> {
	const url = resolveArtifactUrl(manifest, manifest.artifacts.members);
	const response = await fetch(url);
	if (!response.ok) {
		throw new Error(`failed to fetch members at ${url}: ${response.status} ${response.statusText}`);
	}
	return (await response.json()) as MembersIndex;
}
