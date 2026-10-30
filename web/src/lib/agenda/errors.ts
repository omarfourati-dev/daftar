/**
 * Error texts of the daily-work pages: the codes of the appointment, queue and money endpoints (backend report
 * "Vertragsergänzungen") live in `agenda.errors.<code>`; everything else falls back to `apiErrorMessage`.
 */
import { ApiError, apiErrorMessage } from '../api';
import { translate } from '../i18n.svelte';

export function errorText(err: unknown): string {
	if (err instanceof ApiError && err.code) {
		const own = translate(`agenda.errors.${err.code}`);
		if (own) return own;
	}
	return apiErrorMessage(err);
}
