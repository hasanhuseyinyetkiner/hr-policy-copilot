import { useQuery } from "@tanstack/react-query";
import { BookOpen, LayoutDashboard, Library, Menu, Moon, Settings, Sun, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router";
import { api } from "../api.ts";

const LINKS = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/ask", label: "Ask", icon: BookOpen, end: false },
  { to: "/library", label: "Library", icon: Library, end: false },
  { to: "/settings", label: "Settings", icon: Settings, end: false },
];

function initialTheme() {
  return document.documentElement.classList.contains("dark");
}

export function Shell() {
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(initialTheme);
  const overview = useQuery({ queryKey: ["overview"], queryFn: api.overview });

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("hr-theme", next ? "dark" : "light");
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className={open ? "sidebar is-open" : "sidebar"}>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <BookOpen size={18} />
          </span>
          <div>
            <strong>HR Policy Copilot</strong>
            <p>Northwind People</p>
          </div>
        </div>
        <nav id="primary-nav" className="nav-list" aria-label="Primary">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              onClick={() => setOpen(false)}
            >
              <link.icon size={18} aria-hidden="true" />
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div>
            Retrieval{" "}
            <strong>{overview.data ? overview.data.retrieval.mode : "…"}</strong>
          </div>
          <div>Corpus {overview.data ? overview.data.retrieval.corpus_version : "…"}</div>
        </div>
      </aside>
      <div className="workspace">
        <div className="demo-banner">Local demo · synthetic data</div>
        <div className="topbar">
          <button
            className="menu-button rounded-xl border border-[var(--line)] bg-[var(--surface)] px-3 py-2"
            type="button"
            aria-expanded={open}
            aria-controls="primary-nav"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={18} /> : <Menu size={18} />}
            <span className="sr-only">Menu</span>
          </button>
          <p className="m-0 text-sm text-[var(--muted)]">
            Quotes only. Not legal advice.
          </p>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-full border border-[var(--line)] bg-[var(--surface)] px-3 py-2 text-sm"
            onClick={toggleTheme}
            aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
          >
            {dark ? <Sun size={16} /> : <Moon size={16} />}
            {dark ? "Light" : "Dark"}
          </button>
        </div>
        <main id="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
