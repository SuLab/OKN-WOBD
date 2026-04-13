/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // App Router is now stable and default in Next.js 14
  // No experimental config needed
  webpack: (config, { dev, isServer }) => {
    // Disk cache under .next/cache/webpack can get corrupted if .next is partially
    // deleted while `next dev` runs (ENOENT on *.pack.gz, then e[o] is not a function).
    if (dev) {
      config.cache = false;
    }
    // Externalize Node.js built-in modules for client bundle
    // This prevents webpack from trying to bundle fs, path, etc. for the client
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        "fs/promises": false,
        path: false,
        module: false,
      };
      // Mark Node.js built-ins as externals so webpack doesn't try to bundle them
      config.externals = config.externals || [];
      config.externals.push({
        "fs/promises": "commonjs fs/promises",
        fs: "commonjs fs",
      });
    }
    return config;
  },
};

export default nextConfig;






