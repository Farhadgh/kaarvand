import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // keep tracing inside this app (there is an unrelated lockfile on the drive root)
  outputFileTracingRoot: __dirname,
  experimental: {
    // keep server actions predictable with the BFF proxy
    serverActions: { bodySizeLimit: "2mb" },
  },
};

export default nextConfig;
