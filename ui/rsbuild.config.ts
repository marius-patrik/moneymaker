import path from "node:path";
import { defineConfig } from "@rsbuild/core";
import { pluginReact } from "@rsbuild/plugin-react";

export default defineConfig({
  plugins: [pluginReact()],
  html: {
    template: "./index.html",
  },
  source: {
    entry: {
      index: "./src/main.tsx",
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // `moneymaker serve` passes these so both sides agree on ports.
    port: Number(process.env.MONEYMAKER_UI_PORT) || 5173,
    proxy: {
      "/api": {
        target: process.env.MONEYMAKER_API || "http://127.0.0.1:8787",
      },
    },
  },
  output: {
    distPath: {
      root: "dist",
    },
  },
});
