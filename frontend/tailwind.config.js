/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'radar-green': '#00ff00',
        'radar-dark': '#0a1628',
        'alert-critical': '#ef4444',
        'alert-high': '#f97316',
        'alert-medium': '#eab308',
        'alert-low': '#22c55e',
      },
    },
  },
  plugins: [],
}
