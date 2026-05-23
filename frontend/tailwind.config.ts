import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: "#0F766E",
          dark: "#115E59",
          soft: "#CCFBF1",
        },
      },
      fontFamily: {
        uiArabic: ["var(--font-ui-arabic)", "Tajawal", "system-ui", "sans-serif"],
        textArabic: ["var(--font-text-arabic)", "Amiri", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
