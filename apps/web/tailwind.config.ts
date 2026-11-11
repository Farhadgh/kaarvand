import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-vazirmatn)", "Tahoma", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#eef6ff",
          100: "#d9ecff",
          200: "#bcdcff",
          300: "#8ec6ff",
          400: "#59a6ff",
          500: "#3383fb",
          600: "#1e63f0",
          700: "#1a4edc",
          800: "#1c41b2",
          900: "#1c3b8c",
        },
        ink: {
          50: "#f7f8fa",
          100: "#eceef2",
          200: "#d7dbe3",
          300: "#b3bac8",
          400: "#8792a6",
          500: "#66738a",
          600: "#515d72",
          700: "#414b5d",
          800: "#333c4b",
          900: "#1f2633",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.10)",
      },
      borderRadius: {
        xl2: "1rem",
      },
    },
  },
  plugins: [],
};

export default config;
