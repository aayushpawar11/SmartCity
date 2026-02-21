"use client";

import { useState } from "react";

type Props = {
  onSearch: (query: string) => void;
  placeholder?: string;
};

export function SearchBar({ onSearch, placeholder = "Search events..." }: Props) {
  const [q, setQ] = useState("");

  return (
    <form
      className="flex gap-2 flex-1 max-w-md"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(q);
      }}
    >
      <div className="relative flex-1 flex items-center">
        <span className="absolute left-3.5 text-[#64748b] pointer-events-none">
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </span>
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-xl border border-white/10 bg-white/5 pl-10 pr-4 py-2.5 text-sm text-[#f1f5f9] placeholder-[#64748b] focus:border-accent/50 focus:bg-white/[0.07] focus:ring-2 focus:ring-accent/20 transition-all"
        />
      </div>
      <button
        type="submit"
        className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-[#0a0e17] hover:bg-cyan-300 focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-[#0a0e17] transition-all shadow-glow-sm"
      >
        Search
      </button>
    </form>
  );
}
