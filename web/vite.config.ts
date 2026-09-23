import { defineConfig } from "vite";

// The repo's data/ folder is served as static files (menus.json, vendors.json, …).
// SIDGE_DATA_DIR points it elsewhere, e.g. at sample data for local development.
export default defineConfig({
  base: "./",
  publicDir: process.env.SIDGE_DATA_DIR ?? "../data",
});
