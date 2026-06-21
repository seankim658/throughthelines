/**
 * Editorial copy for the /changelog page.
 */

/** One release and its notable changes. */
export interface ChangelogEntry {
	version: string;
	date: string;
	changes: readonly string[];
}

/** The release history, newest first. */
export const CHANGELOG: readonly ChangelogEntry[] = [
	{
		version: 'v0.5.0',
		date: '2026-06-20',
		changes: [
			'Initial public release.',
			'Address-based, longitudinal congressional-district lookup for North Carolina, covering the 107th through 119th Congresses (2001–2026).'
		]
	}
];

/** Format an ISO calendar date ("YYYY-MM-DD") as e.g. "June 20, 2026". */
export function formatEntryDate(isoDate: string): string {
	const [year, month, day] = isoDate.split('-').map(Number);
	const date = new Date(Date.UTC(year, month - 1, day));
	return date.toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'long',
		day: 'numeric',
		timeZone: 'UTC'
	});
}
