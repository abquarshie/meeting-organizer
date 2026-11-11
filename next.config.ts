import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// The screens' wording comes from messages/en.json and messages/ada.json (Dangme), picked in src/i18n/request.ts.
const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// Sent with every page: no framing by other sites, no guessing file types, and no camera, microphone or location.
const SECURITY_HEADERS = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  // the pg driver and Prisma's generated client run on the server only
  serverExternalPackages: ["pg", "@prisma/adapter-pg"],
  // On Vercel, /api/py is the Python function in api/py.py. Locally, `npm run dev:py` serves it on port 8001.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/py", destination: "http://127.0.0.1:8001/api/py" }];
  },
};

export default withNextIntl(nextConfig);
