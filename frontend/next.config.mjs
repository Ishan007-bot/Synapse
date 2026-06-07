/** @type {import('next').NextConfig} */
const nextConfig = {
  // react-force-graph-2d's internals (vasturiano/force-graph) can't tolerate
  // React's StrictMode double-mount in dev — it leaves dangling canvas refs
  // and crashes with "Cannot read properties of null (reading 'removeChild')".
  // Off in dev too; this is purely a dev-mode double-invoke check.
  reactStrictMode: false,
  // The FastAPI backend address — override with NEXT_PUBLIC_API_BASE if you
  // run uvicorn on a different host/port.
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000",
  },
};

export default nextConfig;
