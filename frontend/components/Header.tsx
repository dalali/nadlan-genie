"use client";

export function Header({ version }: { version?: string }) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-semibold tracking-tight">
            nadlan-genie
          </span>
          {version && (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
              v{version}
            </span>
          )}
        </div>
        <nav className="flex items-center gap-4 text-sm text-slate-600">
          <a
            href="https://github.com/dalali/nadlan-genie"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-slate-900"
          >
            GitHub
          </a>
          <a
            href="/api/health"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-slate-900"
          >
            health
          </a>
        </nav>
      </div>
    </header>
  );
}
