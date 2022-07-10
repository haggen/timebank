import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import tsconfigPaths from "vite-tsconfig-paths";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [tsconfigPaths(), preact()],
  server: {
    host: "0.0.0.0",
    port: parseInt(process.env.PORT || "3000", 10),
  },
  preview: {
    port: parseInt(process.env.PORT || "3000", 10),
  },
});
