/**
 * Theme management.
 *
 * Tracks the user's theme preference (light/dark/system) and applies
 * the resolved theme.
 */

import { browser } from '$app/environment';

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

const STORAGE_KEY = 'theme';

export function getStoredPreference(): ThemePreference {
	if (!browser) return 'system';
	const raw = localStorage.getItem(STORAGE_KEY);
	if (raw === 'light' || raw === 'dark') return raw;
	return 'system';
}

export function resolvePreference(preference: ThemePreference): ResolvedTheme {
	if (preference !== 'system') return preference;
	if (!browser) return 'light';
	return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function applyTheme(resolved: ResolvedTheme): void {
	if (!browser) return;
	if (resolved === 'dark') {
		document.documentElement.setAttribute('data-theme', 'dark');
	} else {
		document.documentElement.removeAttribute('data-theme');
	}
}

export function setPreference(preference: ThemePreference): void {
	if (!browser) return;
	if (preference === 'system') {
		localStorage.removeItem(STORAGE_KEY);
	} else {
		localStorage.setItem(STORAGE_KEY, preference);
	}
	applyTheme(resolvePreference(preference));
}
