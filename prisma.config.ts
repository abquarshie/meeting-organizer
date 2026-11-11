import "dotenv/config";
import { defineConfig } from "prisma/config";

// Prisma only reads and writes the tables here. They are created by db/schema.sql (`npm run db:setup`, which every
// build runs), so there are no Prisma migrations: never run `prisma migrate` or `prisma db push`. When a table
// changes, change db/schema.sql and prisma/schema.prisma together.
export default defineConfig({
  schema: "prisma/schema.prisma",
  // `prisma generate` (run on every install) needs no database
  datasource: { url: process.env.DATABASE_URL ?? "" },
});
