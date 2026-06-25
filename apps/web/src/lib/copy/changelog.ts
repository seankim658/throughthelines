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
		version: 'v0.6.0',
		date: '2026-06-25',
		changes: [
			'Extended North Carolina coverage through the 120th Congress, adding the 2025 mid-decade map (SL 2025-95). The congressional districts on the 2026 ballot.',
			'Generalized boundary sourcing beyond the Lewis archive, so a plan can be mapped a cycle before the archive catches up. The 120th map is sourced from the North Carolina General Assembly.',
			'Each plan now records the publisher of its district boundaries, shown on the plan detail panel.'
		]
	},
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
