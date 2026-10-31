import { defineConfig } from 'vitest/config';
import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig(({ mode }) => ({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) => (filename.includes('node_modules') ? undefined : true)
			},
			/**
			 * SPA: FastAPI serves build/ and answers every app route (/app, /connexion, /invitation, /salle/…,
			 * /ticket/…) with 200.html. "/" belongs to the landing site, so there is no index.html here.
			 */
			adapter: adapter({ pages: 'build', assets: 'build', fallback: '200.html', strict: false })
		})
	],
	// Local backend: `PORT=18084 python -m daftar` (port 8080 is taken on Omar's machine), or the Docker stack.
	server: { proxy: { '/api': process.env.API_URL ?? 'http://localhost:18084' } },
	// Never inline fonts as data: URIs – the CSP allows fonts only from 'self' (found by the E2E console check).
	build: { assetsInlineLimit: 0 },
	// Svelte must resolve to its browser build so components can be mounted in jsdom.
	resolve: mode === 'test' ? { conditions: ['browser'] } : undefined,
	test: {
		expect: { requireAssertions: true },
		// cold dynamic imports (i18n.test resets modules) can take > 5 s while the whole suite runs in parallel
		testTimeout: 20_000,
		environment: 'jsdom',
		include: ['src/**/*.{test,spec}.{js,ts}', 'scripts/**/*.test.ts'],
		setupFiles: ['./src/vitest-setup.ts']
	}
}));
