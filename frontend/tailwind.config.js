/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: '#0a0a0f',
          'bg-secondary': '#0d1117',
          card: '#111827',
          elevated: '#1a2332',
          border: '#1e2d3d',
          'border-accent': 'rgba(0, 212, 255, 0.13)',
        },
        accent: {
          cyan: '#00d4ff',
          green: '#00ff88',
          amber: '#ffaa00',
          red: '#ff4444',
          purple: '#a855f7',
        },
        text: {
          primary: '#e2e8f0',
          secondary: '#94a3b8',
          muted: '#475569',
        },
      },
      fontFamily: {
        data: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
        ui: ['"Inter"', 'system-ui', 'sans-serif'],
      },
      animation: {
        'ticker-scroll': 'ticker-scroll 60s linear infinite',
      },
      keyframes: {
        'ticker-scroll': {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
};
