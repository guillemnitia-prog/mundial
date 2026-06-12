/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // La API JSON (FastAPI) corre aparte; el front la llama con credentials:"include".
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
};

export default nextConfig;
