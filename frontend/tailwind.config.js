/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          pink: "#FF97AD",
          blue: "#5171FF",
        },
        navy: {
          50: "#f0f3ff",
          100: "#d9e0f5",
          200: "#a8b5db",
          300: "#7889c1",
          400: "#4d62a8",
          500: "#2d3e7a",
          600: "#1e2d5e",
          700: "#162147",
          800: "#0f1830",
          900: "#0a1020",
        },
        dark: {
          50: "#2a2f3e",
          100: "#232836",
          200: "#1e2230",
          300: "#191d2a",
          400: "#141723",
          500: "#10131d",
          600: "#0c0e17",
          700: "#080a11",
        },
        beige: {
          50: "#fefcf8",
          100: "#fdf8ef",
          200: "#faf0de",
          300: "#f5e6c8",
          400: "#e8d4a8",
        },
      },
      animation: {
        "fade-in": "fadeIn 0.5s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
}
