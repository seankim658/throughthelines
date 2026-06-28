import { resolveArtifactUrl } from '$lib/manifest/loader';
import type { Manifest } from '$lib/manifest/types';
import type { PlanIndex } from './types';
import { fetchVersionedJson } from '$lib/fetch-json';

const _PLAN_INDEX_SCHEMA_VERSION = 1;

export async function loadPlanIndex(
	manifest: Manifest,
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<PlanIndex> {
	const url = resolveArtifactUrl(manifest, manifest.artifacts.plan_index);
	return fetchVersionedJson<PlanIndex>(url, 'plan_index', _PLAN_INDEX_SCHEMA_VERSION, fetch);
}
