import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16's dev server refuses to hydrate pages opened from any hostname
  // other than "localhost" (the page loads but stays dead: inputs and buttons
  // do nothing). 127.0.0.1 is the usual way someone ends up on a different
  // hostname by accident. Dev-only; has no effect on `next build`/Vercel.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
