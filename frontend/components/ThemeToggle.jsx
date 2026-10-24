"use client";
import { Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    setDark(document.documentElement.dataset.theme === "dark");
  }, []);
  return (
    <button
      className="theme-toggle"
      type="button"
      aria-label="حالت تیره"
      aria-pressed={dark}
      title={dark ? "فعال کردن حالت روشن" : "فعال کردن حالت تیره"}
      onClick={() => {
        const next =
          document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        setDark(next === "dark");
        try {
          localStorage.setItem("snack-theme", next);
        } catch {
          /* Theme still works when storage is blocked. */
        }
      }}
    >
      {dark ? (
        <Sun size={20} aria-hidden="true" />
      ) : (
        <Moon size={20} aria-hidden="true" />
      )}
    </button>
  );
}
