/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          0: '#0a0e14',
          1: '#0d1117',
          2: '#151b23',
          3: '#1c232d',
        },
        accent: {
          primary: '#00d4ff',
          'primary-dim': 'rgba(0, 212, 255, 0.25)',
          secondary: '#0891b2',
        },
        status: {
          nominal: '#10b981',
          caution: '#f59e0b',
          warning: '#f97316',
          critical: '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Barlow', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
    },
  },
  plugins: [],
}
