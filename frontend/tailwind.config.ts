import type { Config } from "tailwindcss";

// Tokens de DESIGN.md (negro/verde). Mobile-only.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A0A0A",
        surface: "#141414",
        border: "#262626",
        accent: "#00E676",
        accentHover: "#00C853",
        accentFaint: "#00E67620",
        fg: "#F5F5F5",
        muted: "#A3A3A3",
        positive: "#00E676",
        negative: "#FF5252",
        warning: "#FFB300",
      },
      borderRadius: {
        card: "18px",
        btn: "12px",
      },
      fontFamily: {
        sans: ["Inter", "Geist", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
