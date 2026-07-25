import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        nhl: {
          red: "#C8102E",
          dark: "#000000",
          gray: "#F2F2F2",
          white: "#FFFFFF",
        },
      },
    },
  },
  plugins: [],
};

export default config;