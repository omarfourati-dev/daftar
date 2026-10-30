import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests against the Docker stack: `docker compose --profile app up -d --build` (app on port 18083,
 * BASE_DOMAIN=localhost so practice sub-domains work as `<slug>.localhost:18083`).
 */
export default defineConfig({
	testDir: './e2e',
	timeout: 60_000,
	expect: { timeout: 15_000 },
	retries: process.env.CI ? 1 : 0,
	workers: 1, // one shared database; the login throttle is per IP
	reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
	use: {
		baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:18083',
		locale: 'fr-FR',
		timezoneId: 'Africa/Tunis',
		trace: 'retain-on-failure'
	},
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]
});
