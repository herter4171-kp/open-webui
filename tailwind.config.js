import typography from '@tailwindcss/typography';
import containerQueries from '@tailwindcss/container-queries';

/** @type {import('tailwindcss').Config} */
export default {
	darkMode: 'class',
	content: ['./src/**/*.{html,js,svelte,ts}'],
	theme: {
		extend: {
			typography: {
				DEFAULT: {
					css: {
						pre: false,
						code: false,
						'pre code': false,
						'code::before': false,
						'code::after': false
					}
				}
			},
			padding: {
				'safe-bottom': 'env(safe-area-inset-bottom)'
			},
			transitionProperty: {
				width: 'width'
			},
			// KP ADD
			fontFamily: {
				// Your Custom Sans-Serif Stack
				sans: [
				'Segoe UI',       // <--- Your #1 Priority for Windows
				'Arial',          // <--- Fallback
				'ui-sans-serif',  // <--- Tailwind defaults below...
				'system-ui',
				'sans-serif',
				'Apple Color Emoji',
				'Segoe UI Emoji', 
				'Segoe UI Symbol', 
				'Noto Color Emoji'
				],
				// Your Custom Monospace Stack
				mono: [
				'Consolas',       // <--- Your #1 Priority for Windows
				'Lucida Console', // <--- Fallback
				'ui-monospace',
				'SFMono-Regular', 
				'Menlo', 
				'Monaco', 
				'Liberation Mono', 
				'Courier New', 
				'monospace'
				],
			}
			// END KP ADD
		}
	},
	plugins: [typography, containerQueries]
};
