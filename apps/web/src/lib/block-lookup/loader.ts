import { resolveArtifactUrl } from '$lib/manifest/loader';
import type { Manifest } from '$lib/manifest/types';
import type { BlockLookup } from './types';
import { fetchVersionedJson } from '$lib/fetch-json';

const _BLOCK_LOOKUP_SCHEMA_VERSION = 1;
const _CHAMBER = 'congressional';

/**
 * Fetch and parse block_lookup_{STATE}.json for the given state code.
 */
export async function loadBlockLookup(
	manifest: Manifest,
	state: string,
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<BlockLookup> {
	const stateSection = manifest.states[state];
	if (stateSection === undefined) {
		throw new Error(`block_lookup: state ${state} is not in this build's manifest`);
	}

	const chamberSection = stateSection.chambers[_CHAMBER];
	if (chamberSection === undefined) {
		throw new Error(
			`block_lookup: state ${state} has no ${_CHAMBER} chamber section in the manifest`
		);
	}

	const url = resolveArtifactUrl(manifest, chamberSection.artifacts.block_lookup);
	return fetchVersionedJson<BlockLookup>(url, 'block_lookup', _BLOCK_LOOKUP_SCHEMA_VERSION, fetch);
}
