import { defineConfig } from "cf/config";

export default defineConfig({
  worker: {
    name: "plectrum-press",
    compatibilityDate: "2026-10-23",
    assets: {
      // A page is `x/index.html` and every link says `x`, so `x` is the address.
      htmlHandling: "drop-trailing-slash",
      notFoundHandling: "404-page",
    },
    domains: ["plectrum.press"],
    workersDev: false,
    observability: { enabled: true },
  },
});
