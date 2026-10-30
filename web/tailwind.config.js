/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        oranje: { DEFAULT: '#FF6200', 50: '#FFF3EB', 100: '#FFE2CC', 600: '#E55800' },
        navy: { DEFAULT: '#001E82', 50: '#EEF1FA', 100: '#D6DDF2', 900: '#00124F' },
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
    },
  },
  plugins: [],
}
