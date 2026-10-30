/**
 * Installing the practice app (section 13): keeps the browser's `beforeinstallprompt` event (it fires once, early,
 * on any page – so this module is imported by the /app layout) and knows the platform for the instructions.
 */
export type Platform = 'ios' | 'android' | 'desktop';

interface InstallPromptEvent extends Event {
	prompt(): Promise<void>;
	userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

/** Swappable in tests. */
export const installDeps = {
	userAgent: (): string => (typeof navigator === 'undefined' ? '' : navigator.userAgent),
	standalone: (): boolean =>
		typeof window !== 'undefined' &&
		((typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) ||
			(navigator as Navigator & { standalone?: boolean }).standalone === true)
};

export function platform(ua: string = installDeps.userAgent()): Platform {
	if (/iPhone|iPad|iPod/i.test(ua) || (/Macintosh/i.test(ua) && /Mobile/i.test(ua))) return 'ios';
	if (/Android/i.test(ua)) return 'android';
	return 'desktop';
}

class Install {
	prompt = $state<InstallPromptEvent | null>(null);
	installed = $state(false);

	constructor() {
		globalThis.addEventListener?.('beforeinstallprompt', (e: Event) => {
			e.preventDefault();
			this.prompt = e as InstallPromptEvent;
		});
		globalThis.addEventListener?.('appinstalled', () => {
			this.installed = true;
			this.prompt = null;
		});
	}

	/** Shows the browser's own install dialog; true when the user accepted. */
	async ask(): Promise<boolean> {
		const event = this.prompt;
		if (!event) return false;
		this.prompt = null;
		await event.prompt();
		const choice = await event.userChoice;
		if (choice.outcome === 'accepted') this.installed = true;
		return choice.outcome === 'accepted';
	}

	/** For tests. */
	reset() {
		this.prompt = null;
		this.installed = false;
	}
}

export const install = new Install();
