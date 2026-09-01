/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Main theme colors - Changed to white/black theme
        'ravia-purple': {
          900: '#FFFFFF', // White background
          800: '#F8F9FA',
          700: '#E9ECEF',
          600: '#DEE2E6',
          500: '#CED4DA', // Base gray
          400: '#ADB5BD',
          300: '#6C757D',
          200: '#495057',
          100: '#343A40', // Dark gray
        },
        'ravia-cyan': {
          500: '#000000', // Black accent
          400: '#212529',
          300: '#343A40',
          200: '#495057',
          100: '#6C757D',
        },
        'ravia-pink': {
          500: '#000000', // Black accent
          400: '#212529',
          300: '#343A40',
          200: '#495057',
          100: '#6C757D',
        },
        // Legacy colors for backward compatibility - Updated to white/black
        'custom-purple': '#FFFFFF',
        'custom-purple-light': '#F8F9FA',
        'custom-purple-dark': '#E9ECEF',
      },
      backgroundImage: {
        'ravia-gradient': 'linear-gradient(to right, #FFFFFF, #F8F9FA, #E9ECEF)',
        'ravia-gradient-vertical': 'linear-gradient(to bottom, #FFFFFF, #F8F9FA, #E9ECEF)',
        'ravia-accent-gradient': 'linear-gradient(to right, #000000, #343A40)',
      },
      boxShadow: {
        'ravia-glow': '0 0 15px rgba(0, 0, 0, 0.1)',
        'ravia-glow-cyan': '0 0 15px rgba(0, 0, 0, 0.1)',
      },
      borderRadius: {
        'ravia': '0.75rem',
      },
    },
  },
  plugins: [],
}
