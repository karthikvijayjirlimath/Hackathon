/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#0ea5e9',
          hover: '#0284c7',
          light: '#f0f9ff',
        },
        secondary: {
          DEFAULT: '#6366f1',
        },
        success: {
          DEFAULT: '#10b981',
        },
        danger: {
          DEFAULT: '#ef4444',
        }
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
