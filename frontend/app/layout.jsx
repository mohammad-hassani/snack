import "./globals.css";
import "./redesign.css";
import ThemeToggle from "../components/ThemeToggle";
export const metadata = {
  title: "اسنک · هماهنگ‌تر با هم",
  icons: { icon: "/static/chat/logo.svg", apple: "/static/chat/logo.svg" },
  description: "گفتگوهای تیم شما در یک فضای کاری",
};
export default function Layout({ children }) {
  return (
    <html lang="fa" dir="rtl" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(() => {
          let theme;
          try { theme = localStorage.getItem('snack-theme'); } catch {}
          document.documentElement.dataset.theme = theme === 'dark' || theme === 'light'
            ? theme : matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        })();`,
          }}
        />
        <link rel="stylesheet" href="/static/chat/style.css" />
      </head>
      <body>
        <ThemeToggle />
        {children}
      </body>
    </html>
  );
}
