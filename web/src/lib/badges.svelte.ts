/**
 * Counters in the navigation (story C2): online requests to confirm and overdue appointments ("Non venus ?") next to
 * "Aujourd'hui", products to order next to "Stock" (spec stock-hygiène 8), from `GET /api/badges`, refreshed every
 * 60 s while the app is open and right after the desk handled one.
 */
import { api } from './api';
import type { Badges as BadgeCounts } from './types/agenda';

const EVERY_MS = 60_000;

export class Badges {
	onlineRequests = $state(0);
	overdue = $state(0);
	stockToOrder = $state(0);
	private timer: ReturnType<typeof setInterval> | null = null;

	get total(): number {
		return this.onlineRequests + this.overdue;
	}

	async refresh(): Promise<void> {
		try {
			const counts = await api<BadgeCounts>('/api/badges');
			this.onlineRequests = counts.onlineRequests ?? 0;
			this.overdue = counts.overdue ?? 0;
			this.stockToOrder = counts.stockToOrder ?? 0;
		} catch {
			/* offline or a short server hiccup: keep the last counts */
		}
	}

	start(): void {
		if (this.timer) return;
		void this.refresh();
		this.timer = setInterval(() => void this.refresh(), EVERY_MS);
	}

	stop(): void {
		if (this.timer) clearInterval(this.timer);
		this.timer = null;
	}
}

export const badges = new Badges();
