const API_PROXY_TARGET = process.env.API_PROXY_TARGET || "https://mundial-1jhc.onrender.com";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
  // Proxy same-origin: el navegador llama a /api/* en el propio dominio de Vercel y Next lo
  // reenvía al backend. Así la cookie de sesión es "first-party" y no la bloquea el navegador
  // (clave en iPhone/Safari, que bloquea cookies de terceros entre dominios distintos).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_PROXY_TARGET}/:path*` }];
  },
};

export default nextConfig;
