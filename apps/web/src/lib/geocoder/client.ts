/**
 * Browser-side geocoder against the U.S. Census Geocoding Services API.
 *
 * API reference:
 *  https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html
 */

import type { CensusAddressMatch, CensusResponse, GeocodeMatch, GeocodeResult } from './types';

// --- Configuration ---

const ENDPOINT = 'https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress';
/** Current MAF/TIGER address dataset.  */
const BENCHMARK = 'Public_AR_Current';
/** 2020 Census geographies. Matches the GEOID space used by block_lookup_*.json. */
const VINTAGE = 'Census2020_Current';
const TIMEOUT_MS = 10_000;

// --- Cache ---

/**
 * Session-lifetime cache, keyed on normalized address.
 */
const cache = new Map<string, GeocodeResult>();

function normalizedAddress(address: string): string {
	return address.trim().toLowerCase().replace(/\s+/g, ' ');
}

// --- JSONP Transport ---

class GeocodeTimeoutError extends Error {}
class GeocodeNetworkError extends Error {}

/**
 * Generic JSONP fetcher. Resolves with whatever the server returns.
 *
 * Lifecycle:
 *   1. Generate a unique callback name.
 *   2. Register window[callbackName] as our resolver.
 *   3. Append <script src="...&callback=name"> to the document.
 *   4. Wait for callback / script error / timeout (whatever comes first).
 *   5. Clean up script tag + global function regardless of outcome.
 */
function jsonpFetch(url: URL, timeoutMs: number): Promise<unknown> {
	return new Promise((resolve, reject) => {
		const callbackName = `_ttl_geocode_${crypto.randomUUID().replace(/-/g, '')}`;
		const script = document.createElement('script');
		const globals = window as unknown as Record<string, unknown>;
		let settled = false;

		const cleanup = (): void => {
			delete globals[callbackName];
			script.remove();
		};

		const timeoutId = window.setTimeout(() => {
			if (settled) return;
			cleanup();
			reject(new GeocodeTimeoutError());
		}, timeoutMs);

		globals[callbackName] = (response: unknown): void => {
			if (settled) return;
			settled = true;
			window.clearTimeout(timeoutId);
			cleanup();
			resolve(response);
		};

		script.onerror = (): void => {
			if (settled) return;
			settled = true;
			window.clearTimeout(timeoutId);
			cleanup();
			reject(new GeocodeNetworkError());
		};

		const requestUrl = new URL(url.toString());
		requestUrl.searchParams.set('callback', callbackName);
		script.src = requestUrl.toString();
		document.head.appendChild(script);
	});
}

// --- Runtime Validation ---

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null;
}

/** Validates the outer envelope. */
function validateResponse(raw: unknown): CensusResponse | null {
	if (!isObject(raw)) return null;
	if (!isObject(raw.result)) return null;
	if (!Array.isArray(raw.result.addressMatches)) return null;
	return raw as unknown as CensusResponse;
}

/**
 * Validates one addressMatch and projects it to a GeocodeMatch.
 */
function buildMatch(match: unknown): GeocodeMatch | null {
	if (!isObject(match)) return null;
	if (typeof match.matchedAddress !== 'string') return null;
	if (!isObject(match.coordinates)) return null;
	if (typeof match.coordinates.x !== 'number') return null;
	if (typeof match.coordinates.y !== 'number') return null;
	if (!isObject(match.addressComponents)) return null;
	if (typeof match.addressComponents.state !== 'string') return null;
	if (!isObject(match.geographies)) return null;

	const blocks = match.geographies['Census Blocks'];
	if (!Array.isArray(blocks) || blocks.length === 0) return null;

	const block = blocks[0];
	if (!isObject(block) || typeof block.GEOID !== 'string') return null;
	if (!/^\d{15}$/.test(block.GEOID)) return null;

	return {
		status: 'match',
		geoid: block.GEOID,
		matchedAddress: match.matchedAddress,
		state: match.addressComponents.state,
		// Census GIS convention: x = longitude, y = latitude.
		coordinates: { lat: match.coordinates.y, lng: match.coordinates.x }
	};
}

// --- Public API ---

/**
 * Geocode an address to a 2020 Census block GEOID.
 */
export async function geocode(address: string): Promise<GeocodeResult> {
	const key = normalizedAddress(address);
	if (key.length === 0) {
		return { status: 'no_match' };
	}

	const cached = cache.get(key);
	if (cached) return cached;

	const url = new URL(ENDPOINT);
	url.searchParams.set('address', address);
	url.searchParams.set('benchmark', BENCHMARK);
	url.searchParams.set('vintage', VINTAGE);
	url.searchParams.set('format', 'jsonp');

	let raw: unknown;
	try {
		raw = await jsonpFetch(url, TIMEOUT_MS);
	} catch (error) {
		if (error instanceof GeocodeTimeoutError) {
			return {
				status: 'error',
				kind: 'timeout',
				message: 'The Census Geocoder did not respond in time. Please try again.'
			};
		}
		if (error instanceof GeocodeNetworkError) {
			return {
				status: 'error',
				kind: 'network',
				message: 'Could not reach the Census Geocoder. Check your connection and try again.'
			};
		}
		return {
			status: 'error',
			kind: 'network',
			message: 'Geocoder request failed'
		};
	}

	const parsed = validateResponse(raw);
	if (!parsed) {
		console.warn('geocode: malformed Census response', raw);
		return {
			status: 'error',
			kind: 'malformed_response',
			message: 'The Census Geocoder returned an unexpected response'
		};
	}

	if (parsed.result.addressMatches.length === 0) {
		const result: GeocodeResult = { status: 'no_match' };
		cache.set(key, result);
		return result;
	}

	const matches: CensusAddressMatch[] = parsed.result.addressMatches;
	const built = buildMatch(matches[0]);
	if (!built) {
		// First match exists but lacks a usable 2020 block, log for visibility
		// but don't cache.
		console.warn('geocode: first match missing 2020 block', matches[0]);
		return { status: 'no_match' };
	}

	cache.set(key, built);
	return built;
}
