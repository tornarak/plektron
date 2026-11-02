import { defineWranglerConfig } from "wrangler/experimental-config";

export default defineWranglerConfig({
  assetsDirectory: process.env.SITE_OUT ?? "../../dist",
});
