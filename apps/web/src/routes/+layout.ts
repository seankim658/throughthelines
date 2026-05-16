/**
 * Root layout loader.
 *
 * Loads the manifest once at the top of the route tree and exposes it to every child
 * layout and page via the `data` prop.
 */

import { loadManifest } from '$lib/manifest/loader';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async ({ fetch }) => {
	const manifest = await loadManifest(fetch);
	return { manifest };
};
