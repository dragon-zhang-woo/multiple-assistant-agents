import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  reactStrictMode: true,
  webpack: (config) => {
    config.cache = false;
    config.resolve = config.resolve ?? {};
    config.resolve.symlinks = false;
    return config;
  }
};

export default nextConfig;
