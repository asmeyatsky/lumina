import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#1e3a5f",
          50: "#e8edf3",
          100: "#c5d1e0",
          200: "#9fb3cc",
          300: "#7995b8",
          400: "#5c7ea8",
          500: "#1e3a5f",
          600: "#1a3355",
          700: "#152b48",
          800: "#10223b",
          900: "#0b192e",
        },
        accent: {
          DEFAULT: "#00d4ff",
          50: "#e0f9ff",
          100: "#b3f0ff",
          200: "#80e6ff",
          300: "#4dddff",
          400: "#26d8ff",
          500: "#00d4ff",
          600: "#00abe6",
          700: "#0083b3",
          800: "#005c80",
          900: "#00354d",
        },
        surface: "#0a1628",
        card: "#111d32",
        success: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
