import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: { cpus: 2 },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
