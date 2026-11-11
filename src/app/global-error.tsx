"use client";
import "@fontsource-variable/inter/wght.css";
import "./globals.css";

// The last resort, when even the page frame failed. It replaces the whole document, so it brings its own html and body,
// and it sits outside the translations, so it reads the message files itself and shows the English and the Dangme.
import en from "../../api/messages/en.json";
import ada from "../../api/messages/ada.json";

const both = (en: string, ada: string) => (ada && ada !== en ? `${en} / ${ada}` : en);
export default function GlobalError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <html lang="en">
      <body>
        <main className="grid min-h-dvh place-items-center px-4">
          <div className="card grid w-full max-w-sm gap-3 text-center">
            <h1 className="m-0 text-xl font-bold">{both(en.err.global_title, ada.err.global_title)}</h1>
            <p className="m-0 text-sm text-muted">{both(en.err.global_body, ada.err.global_body)}</p>
            <div className="btns justify-center">
              <button type="button" className="btn primary" onClick={() => retry()}>{both(en.common.try_again, ada.common.try_again)}</button>
              <a className="btn" href="/">{both(en.common.go_home, ada.common.go_home)}</a>
            </div>
          </div>
        </main>
      </body>
    </html>
  );
}
