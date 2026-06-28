import { resolveArtifactUrl } from '$lib/manifest/loader';
import type { Manifest } from '$lib/manifest/types';
import type { MembersIndex } from './types';
import { fetchJson } from '$lib/fetch-json';

export async function loadMembers(
	manifest: Manifest,
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<MembersIndex> {
	const url = resolveArtifactUrl(manifest, manifest.artifacts.members);
	return fetchJson<MembersIndex>(url, 'members', fetch);
}
