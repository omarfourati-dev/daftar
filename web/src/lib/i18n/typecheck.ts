/**
 * Type-level tests, verified by `npm run check` (svelte-check): if the dictionary typing ever stopped catching
 * these mistakes, the `@ts-expect-error` lines would become unused and fail the check.
 */
import type { Messages } from './fr';
import type { MessageKey } from '../i18n.svelte';

// @ts-expect-error – an Arabic namespace without all keys of the French one is an error
export const missingKey: Messages['nav'] = { label: '', today: '' };

export const extraKey: Messages['roles'] = {
	admin: '',
	owner: '',
	dentist: '',
	assistant: '',
	// @ts-expect-error – a key that French does not have is an error too
	boss: ''
};

export const knownKey: MessageKey = 'auth.submit';
// @ts-expect-error – t() only accepts existing keys
export const unknownKey: MessageKey = 'auth.nope';
// @ts-expect-error – a namespace is not a text
export const namespaceKey: MessageKey = 'auth';
