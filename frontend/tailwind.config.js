/** @type {import('tailwindcss').Config} */
// Soft, warm dark theme: low-contrast graphite surfaces, muted earthy accents.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#1a1b1e',     // page / map background
        hull: '#1f2124',     // top bar
        panel: '#222428',    // side panels
        card: '#2a2c31',     // raised surfaces
        rim: '#323439',      // soft dividers
        rim2: '#3c3f45',     // control borders
        ink: '#e2ded8',      // primary text (warm off-white, not pure white)
        dim: '#aaa49c',
        faint: '#7d7871',
        signal: '#9dc2b4',   // soft sage: interaction / selection
        ochre: '#d9a982',    // route
        caution: '#d5bf8c',
        alert: '#d59a95',
        rose: '#d79ca5',
        sky: '#a5b9d4',
        violet: '#b8a9d3',
        mint: '#a4c8ae',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        // numbers use Inter's tabular figures instead of a terminal-style monospace
        mono: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: { '2xs': ['0.6875rem', { lineHeight: '1rem' }] },
      borderRadius: { lg: '0.625rem', xl: '1rem', '2xl': '1.25rem' },
      boxShadow: { soft: '0 4px 18px -8px rgba(0,0,0,0.35)' },
    },
  },
  plugins: [],
};
