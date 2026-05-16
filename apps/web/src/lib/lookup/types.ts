/**
 * Lookup state machine for the state page's address-to-timeline flow.
 */

import type { TimelineRow } from '$lib/timeline/types';

export type LookupState =
	| { status: 'idle' }
	| { status: 'geocoding' }
	| { status: 'geocode_error'; message: string }
	| { status: 'no_match' }
	| { status: 'out_of_state'; state: string; matchedAddress: string }
	| { status: 'not_in_block_lookup'; geoid: string; matchedAddress: string }
	| { status: 'ready'; matchedAddress: string; geoid: string; rows: TimelineRow[] };
