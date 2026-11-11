import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";
import "@fontsource-variable/inter/wght.css"; // self-hosted, so no request to Google and no layout shift
import { Toaster } from "@/components/Toaster";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("app");
  return {
    title: { default: t("name"), template: `%s · ${t("name")}` },
    description: t("description"),
  };
}

export const viewport: Viewport = {
  width: "device-width", initialScale: 1, viewportFit: "cover",
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#F7F4F9" },
    { media: "(prefers-color-scheme: dark)", color: "#120C17" }],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <html lang={locale === "ada" ? "ada" : "en-GB"}>
      <body>
        <NextIntlClientProvider><Toaster>{children}</Toaster></NextIntlClientProvider>
      </body>
    </html>
  );
}
