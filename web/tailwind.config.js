/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0B1220',
        surface: '#0F1A2B',
        border: '#1F2A3D',
        text: '#E5E7EB',
        muted: '#9CA3AF',
        accent: '#3B82F6',
        success: '#22C55E',
        danger: '#EF4444'
      }
    }
  },
  plugins: []
}
