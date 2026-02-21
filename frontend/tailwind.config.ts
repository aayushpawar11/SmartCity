import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      colors: {
        accent: "#22d3ee",
        "accent-dim": "var(--accent-dim)",
        danger: "#f43f5e",
        surface: "#0f172a",
      },
      borderRadius: {
        panel: "var(--radius)",
        "panel-lg": "var(--radius-lg)",
      },
      boxShadow: {
        glow: "var(--shadow-glow)",
        "glow-sm": "0 0 20px -5px rgba(34, 211, 238, 0.2)",
      },
    },
  },
  plugins: [],
};
export default config;
