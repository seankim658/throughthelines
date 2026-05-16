/**
 * Types for the geocoder layer.
 *
 * Two type families:
 *   - GeocodeResult - the discriminated union throughthelines consumes
 *   - Census*       - narrow types mirroring the subset of the Census Geocoder JSON response
 *
 * Census API reference:
 *   https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html
 */

// --- Public API ---

/**
 * Outcome fo a single geocode  call.
 *
 * Discriminated on `status`. Consumers must handle every variant.
 */
export type GeocodeResult = GeocodeMatch | GeocodeNoMatch | GeocodeError;

/** A successful geocode with a usable 2020 Census block. */
export interface GeocodeMatch {
	status: 'match';
	/** 15-digit 2020 Census block GEOID. Serves as the has key into block_lookup_*.json. */
	geoid: string;
	/** Census's normalized rendering of the input */
	matchedAddress: string;
	/** USPS 2-letter state code. */
	state: string;
	/** Census-interpolated point. */
	coordinates: { lat: number; lng: number };
}

/** Census did not return a usable result for the address. */
export interface GeocodeNoMatch {
	status: 'no_match';
}

export interface GeocodeError {
	status: 'error';
	kind: GeocodeErrorKind;
	message: string;
}

export type GeocodeErrorKind = 'timeout' | 'network' | 'malformed_response';

// --- Internal ---

/**
 * Top level Census Geocoder response.
 */
export interface CensusResponse {
	result: {
		addressMatches: CensusAddressMatch[];
	};
}

/** One match within a Census response. */
export interface CensusAddressMatch {
	matchedAddress: string;
	coordinates: { x: number; y: number };
	addressComponents: { state: string };
	geographies: CensusGeographies;
}

/**
 * The `geographies` object returned by the `geographies/` endpoints.
 */
export interface CensusGeographies {
	'Census Blocks': CensusBlock[];
}

export interface CensusBlock {
	GEOID: string;
}
