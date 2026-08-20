import { fileURLToPath } from "node:url";

/** @type {import('next').NextConfig} */
export default {
  reactStrictMode: true,
  typedRoutes: true,
  // Ada package-lock.json lain di luar repo ini (Drive sync folder); pin root
  // supaya Next.js tidak salah menebak workspace.
  outputFileTracingRoot: fileURLToPath(new URL("../..", import.meta.url)),
};
