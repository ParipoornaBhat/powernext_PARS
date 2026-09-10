/** @type {import('next').NextConfig} */
const nextConfig = {
  // Proxy /api/* to the Hono backend. When Hono is not running, Next.js
  // App Router API routes (src/app/api/**) serve as fallback.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:3001/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
