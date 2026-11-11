import "server-only";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@/generated/prisma/client";

// One client per server process. In development Next.js reloads modules on every change, so the client is kept on
// globalThis instead of opening a new pool each time.
const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

function client(): PrismaClient {
  if (!globalForPrisma.prisma) {
    const url = process.env.DATABASE_URL;
    if (!url) throw new Error("DATABASE_URL is not set. Copy .env.example to .env and fill it in.");
    globalForPrisma.prisma = new PrismaClient({ adapter: new PrismaPg({ connectionString: url, max: 5 }) });
  }
  return globalForPrisma.prisma;
}

// Made on first use rather than on import, so the build (which imports every page but queries nothing) needs no
// database.
export const prisma: PrismaClient = new Proxy({} as PrismaClient, {
  get(_target, prop) {
    const c = client();
    const value = Reflect.get(c, prop, c);
    return typeof value === "function" ? value.bind(c) : value;
  },
});

export type Tx = Parameters<Parameters<typeof prisma.$transaction>[0]>[0];
