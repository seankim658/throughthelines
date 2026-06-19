/**
 * Loads the manifest and resolves artifact URLs.
 */

import { PUBLIC_ARTIFACTS_BASE, PUBLIC_ARTIFACTS_LAYOUT } from '$env/static/public';
import type { ArtifactRef, Manifest } from './types';

const _MANIFEST_VERSION = 1;
const MANIFEST_PATH = 'manifest.json';

/** Fetch and parse the manifest. */
export async function loadManifest(
	fetch: typeof globalThis.fetch = globalThis.fetch
): Promise<Manifest> {
	const url = `${PUBLIC_ARTIFACTS_BASE}/${MANIFEST_PATH}`;
	const response = await fetch(url);
	if (!response.ok) {
		throw new Error(
			`failed to fetch manifest at ${url}: ${response.status} ${response.statusText}`
		);
	}
	const manifest = (await response.json()) as Manifest;
	if (manifest.schema_version !== _MANIFEST_VERSION) {
		throw new Error(
			`manifest schema_version ${manifest.schema_version} is not supported by this build`
		);
	}

	// In dev, artifacts are served flat under PUBLIC_ARTIFACTS_BASE
	if (isFlatLayout()) {
		manifest.build.url_prefix = null;
	}
	return manifest;
}

/** Resolve an artifact to the fetch URL. */
export function resolveArtifactUrl(manifest: Manifest, artifact: ArtifactRef): string {
	const prefix = manifest.build.url_prefix;
	if (prefix === null || artifact.unversioned) {
		return `${PUBLIC_ARTIFACTS_BASE}/${artifact.path}`;
	}
	return `${PUBLIC_ARTIFACTS_BASE}/${prefix}/${artifact.path}`;
}

/** True when artifacts are served flat (no version prefix). */
function isFlatLayout(): boolean {
	if (PUBLIC_ARTIFACTS_LAYOUT === 'flat') return true;
	if (PUBLIC_ARTIFACTS_LAYOUT === 'versioned') return false;
	throw new Error(
		`PUBLIC_ARTIFACTS_LAYOUT must be 'flat' or 'versioned'; got ${JSON.stringify(PUBLIC_ARTIFACTS_LAYOUT)}`
	);
}
