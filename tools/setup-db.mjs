// Creates the app's tables in the database named by DATABASE_URL, from db/schema.sql. Safe to run again: it only adds
// what is missing. Run: npm run db:setup (every Vercel build runs it too). Without DATABASE_URL it does nothing.
import "dotenv/config";
import { readFileSync } from "node:fs";
import pg from "pg";

const url = process.env.DATABASE_URL_UNPOOLED || process.env.DATABASE_URL;
if (!url) {
  console.log("db:setup: DATABASE_URL is not set, so no tables were created.");
  process.exit(0);
}
const sql = readFileSync(new URL("../db/schema.sql", import.meta.url), "utf8");
const client = new pg.Client({ connectionString: url, connectionTimeoutMillis: 15_000 });
try {
  await client.connect();
  await client.query(sql);
  const { rows } = await client.query("SELECT count(*)::int AS n FROM information_schema.tables WHERE table_schema = 'public'");
  console.log(`db:setup: the database is ready (${rows[0].n} tables).`);
} catch (e) {
  console.error(`db:setup: couldn't set up the database: ${e.message}`);
  process.exit(1);
} finally {
  await client.end().catch(() => {});
}
