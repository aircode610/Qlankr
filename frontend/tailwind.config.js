/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        void: '#06060a',
        deep: '#0a0a10',
        surface: '#101018',
        elevated: '#16161f',
        hover: '#1c1c28',
        'border-subtle': '#1e1e2a',
        'border-default': '#2a2a3a',
        'text-primary': '#e4e4ed',
        'text-secondary': '#8888a0',
        'text-muted': '#5a5a70',
        accent: '#7c3aed',
        'accent-dim': '#5b21b6',
        'accent-soft': 'rgba(124,58,237,0.15)',
      },
      fontFamily: {
        sans: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 20px rgba(124,58,237,0.4)',
        'glow-soft': '0 0 40px rgba(124,58,237,0.15)',
      },
    },
  },
  plugins: [],
}
