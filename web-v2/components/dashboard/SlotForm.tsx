"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import type { TemplateDefinition } from "@/lib/context-packs/types";
import {
  type OntologyToken,
  ONTOLOGY_ID_TO_LABEL_SLOT,
} from "@/lib/dashboard/ui-only-slots";
import { DEFAULT_MONDO_DESCENDANT_EXPAND_CAP } from "@/lib/ontology/mondo-descendants-ols";
import { isEnsemblGeneStableId } from "@/lib/ontology/gene-identifiers";

const SEARCH_DEBOUNCE_MS = 300;

function ontologyTokensFromValues(
  values: Record<string, string | string[]>,
  idSlot: string
): OntologyToken[] {
  const labelKey = ONTOLOGY_ID_TO_LABEL_SLOT[idSlot];
  if (!labelKey) return [];
  const raw = values[idSlot];
  const ids = Array.isArray(raw)
    ? raw.map((s) => String(s).trim()).filter(Boolean)
    : typeof raw === "string"
      ? raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean)
      : [];
  const labelRaw = values[labelKey];
  const labels = Array.isArray(labelRaw)
    ? labelRaw.map((s) => String(s))
    : typeof labelRaw === "string" && labelRaw.trim()
      ? [labelRaw]
      : [];
  return ids.map((id, i) => ({
    id,
    label: (labels[i] && String(labels[i]).trim()) || id,
  }));
}

interface NCBITaxonSuggestion {
  iri: string;
  shortForm: string;
  taxonId: string;
  label: string;
  matchedSynonym?: string;
}

function OrganismAutocomplete({
  label,
  placeholder,
  value,
  onChange,
  disabled,
  id,
  required,
}: {
  label: string;
  placeholder: string;
  value: OntologyToken[];
  onChange: (tokens: OntologyToken[]) => void;
  disabled?: boolean;
  id: string;
  required?: boolean;
}) {
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<NCBITaxonSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [alreadyAddedLabel, setAlreadyAddedLabel] = useState<string | null>(null);
  const [showSelectFromListHint, setShowSelectFromListHint] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alreadyAddedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectFromListHintTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const DROPDOWN_MAX_H = 280;
  useEffect(() => {
    if (!open || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    setOpenUpward(spaceBelow < DROPDOWN_MAX_H);
  }, [open]);

  useEffect(() => {
    setHighlightedIndex(suggestions.length > 0 ? 0 : -1);
  }, [suggestions]);

  useEffect(() => {
    if (!alreadyAddedLabel) return;
    alreadyAddedTimeoutRef.current = setTimeout(() => setAlreadyAddedLabel(null), 2000);
    return () => {
      if (alreadyAddedTimeoutRef.current) clearTimeout(alreadyAddedTimeoutRef.current);
    };
  }, [alreadyAddedLabel]);

  useEffect(() => {
    if (!showSelectFromListHint) return;
    selectFromListHintTimeoutRef.current = setTimeout(() => setShowSelectFromListHint(false), 2500);
    return () => {
      if (selectFromListHintTimeoutRef.current) clearTimeout(selectFromListHintTimeoutRef.current);
    };
  }, [showSelectFromListHint]);

  const onSelect = useCallback(
    (item: NCBITaxonSuggestion) => {
      const isDuplicate = value.some((t) => t.id === item.taxonId);
      setInput("");
      setSuggestions([]);
      setOpen(false);
      setHighlightedIndex(-1);
      if (isDuplicate) {
        setAlreadyAddedLabel(item.label);
        return;
      }
      onChange([...value, { id: item.taxonId, label: item.label }]);
    },
    [value, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        const trimmed = (e.target as HTMLInputElement).value?.trim() ?? "";
        if (trimmed && open && suggestions.length > 0 && highlightedIndex >= 0) {
          e.preventDefault();
          onSelect(suggestions[highlightedIndex]);
          return;
        }
        if (trimmed) {
          e.preventDefault();
          setShowSelectFromListHint(true);
          return;
        }
      }
      if (!open || suggestions.length === 0) {
        if (e.key === "Escape") setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
      } else if (e.key === "Enter" && highlightedIndex >= 0) {
        e.preventDefault();
        onSelect(suggestions[highlightedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setHighlightedIndex(-1);
      }
    },
    [open, suggestions, highlightedIndex, onSelect]
  );

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    setOpen(true);
    try {
      const res = await fetch(
        `/api/tools/ontology/ncbitaxon/search?q=${encodeURIComponent(q)}&limit=15`
      );
      const data = await res.json();
      setSuggestions(data.results ?? []);
      setOpen(true);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!input.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(input.trim());
      debounceRef.current = null;
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [input, fetchSuggestions]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const remove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  return (
    <div ref={wrapperRef} className="space-y-1 relative">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {required && <sup className="text-red-600 dark:text-red-400 ml-0.5" aria-hidden>*</sup>}
      </label>
      <div className="flex flex-wrap gap-2 items-center rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1.5 min-h-[38px] focus-within:ring-2 focus-within:ring-niaid-header focus-within:border-transparent">
        {value.map((token, i) => (
          <span
            key={`${token.id}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-600 text-slate-800 dark:text-slate-200 text-sm"
          >
            {token.label}
            {!disabled && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="hover:text-red-600 dark:hover:text-red-400 font-medium leading-none"
                aria-label={`Remove ${token.label}`}
              >
                ×
              </button>
            )}
          </span>
        ))}
        <input
          id={id}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder={value.length === 0 ? placeholder : "Add organism…"}
          disabled={disabled}
          className="flex-1 min-w-[120px] px-1 py-0.5 text-sm bg-transparent border-0 border-none outline-none text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-activedescendant={highlightedIndex >= 0 ? `${id}-option-${highlightedIndex}` : undefined}
          role="combobox"
          aria-label={label}
        />
      </div>
      {open && (suggestions.length > 0 || loading) && (
        <ul
          id={`${id}-listbox`}
          role="listbox"
          className={`absolute z-50 w-full max-h-60 overflow-auto rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg ${openUpward ? "bottom-full mb-0.5" : "mt-0.5"}`}
        >
          {loading && suggestions.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">Searching…</li>
          )}
          {suggestions.map((item, i) => (
            <li
              key={item.iri}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === highlightedIndex}
              className={`px-3 py-2 text-sm cursor-pointer text-slate-900 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 last:border-b-0 ${i === highlightedIndex ? "bg-slate-100 dark:bg-slate-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"}`}
              onClick={() => onSelect(item)}
            >
              <span className="font-medium">{item.label}</span>
              <span className="text-slate-500 dark:text-slate-400 ml-1">({item.shortForm})</span>
              {item.matchedSynonym && (
                <span className="block text-xs text-slate-500 dark:text-slate-400 truncate">
                  Synonym: {item.matchedSynonym}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {alreadyAddedLabel && (
        <p className="text-xs text-amber-700 dark:text-amber-400 mt-1" role="status">
          {alreadyAddedLabel} already added.
        </p>
      )}
      {showSelectFromListHint && (
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1" role="status">
          Select an option from the list when suggestions appear.
        </p>
      )}
    </div>
  );
}

interface MondoSuggestion {
  iri: string;
  shortForm: string;
  oboId: string;
  label: string;
  matchedSynonym?: string;
}

function MondoAutocomplete({
  label,
  placeholder,
  value,
  onChange,
  disabled,
  id,
  required,
}: {
  label: string;
  placeholder: string;
  value: OntologyToken[];
  onChange: (tokens: OntologyToken[]) => void;
  disabled?: boolean;
  id: string;
  required?: boolean;
}) {
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<MondoSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [alreadyAddedLabel, setAlreadyAddedLabel] = useState<string | null>(null);
  const [showSelectFromListHint, setShowSelectFromListHint] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alreadyAddedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectFromListHintTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const DROPDOWN_MAX_H = 280;
  useEffect(() => {
    if (!open || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    setOpenUpward(spaceBelow < DROPDOWN_MAX_H);
  }, [open]);

  useEffect(() => {
    setHighlightedIndex(suggestions.length > 0 ? 0 : -1);
  }, [suggestions]);

  useEffect(() => {
    if (!alreadyAddedLabel) return;
    alreadyAddedTimeoutRef.current = setTimeout(() => setAlreadyAddedLabel(null), 2000);
    return () => {
      if (alreadyAddedTimeoutRef.current) clearTimeout(alreadyAddedTimeoutRef.current);
    };
  }, [alreadyAddedLabel]);

  useEffect(() => {
    if (!showSelectFromListHint) return;
    selectFromListHintTimeoutRef.current = setTimeout(() => setShowSelectFromListHint(false), 2500);
    return () => {
      if (selectFromListHintTimeoutRef.current) clearTimeout(selectFromListHintTimeoutRef.current);
    };
  }, [showSelectFromListHint]);

  const onSelect = useCallback(
    (item: MondoSuggestion) => {
      const isDuplicate = value.some((t) => t.id === item.oboId);
      setInput("");
      setSuggestions([]);
      setOpen(false);
      setHighlightedIndex(-1);
      if (isDuplicate) {
        setAlreadyAddedLabel(item.label);
        return;
      }
      onChange([...value, { id: item.oboId, label: item.label }]);
    },
    [value, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        const trimmed = (e.target as HTMLInputElement).value?.trim() ?? "";
        if (trimmed && open && suggestions.length > 0 && highlightedIndex >= 0) {
          e.preventDefault();
          onSelect(suggestions[highlightedIndex]);
          return;
        }
        if (trimmed) {
          e.preventDefault();
          setShowSelectFromListHint(true);
          return;
        }
      }
      if (!open || suggestions.length === 0) {
        if (e.key === "Escape") setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
      } else if (e.key === "Enter" && highlightedIndex >= 0) {
        e.preventDefault();
        onSelect(suggestions[highlightedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setHighlightedIndex(-1);
      }
    },
    [open, suggestions, highlightedIndex, onSelect]
  );

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    setOpen(true);
    try {
      const res = await fetch(
        `/api/tools/ontology/mondo/search?q=${encodeURIComponent(q)}&limit=15`
      );
      const data = await res.json();
      setSuggestions(data.results ?? []);
      setOpen(true);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!input.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(input.trim());
      debounceRef.current = null;
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [input, fetchSuggestions]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const remove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  return (
    <div ref={wrapperRef} className="space-y-1 relative">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {required && <sup className="text-red-600 dark:text-red-400 ml-0.5" aria-hidden>*</sup>}
      </label>
      <div className="flex flex-wrap gap-2 items-center rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1.5 min-h-[38px] focus-within:ring-2 focus-within:ring-niaid-header focus-within:border-transparent">
        {value.map((token, i) => (
          <span
            key={`${token.id}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-600 text-slate-800 dark:text-slate-200 text-sm"
          >
            {token.label}
            {!disabled && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="hover:text-red-600 dark:hover:text-red-400 font-medium leading-none"
                aria-label={`Remove ${token.label}`}
              >
                ×
              </button>
            )}
          </span>
        ))}
        <input
          id={id}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder={value.length === 0 ? placeholder : "Add condition…"}
          disabled={disabled}
          className="flex-1 min-w-[120px] px-1 py-0.5 text-sm bg-transparent border-0 border-none outline-none text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-activedescendant={highlightedIndex >= 0 ? `${id}-option-${highlightedIndex}` : undefined}
          role="combobox"
          aria-label={label}
        />
      </div>
      {open && (suggestions.length > 0 || loading) && (
        <ul
          id={`${id}-listbox`}
          role="listbox"
          className={`absolute z-50 w-full max-h-60 overflow-auto rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg ${openUpward ? "bottom-full mb-0.5" : "mt-0.5"}`}
        >
          {loading && suggestions.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">Searching…</li>
          )}
          {suggestions.map((item, i) => (
            <li
              key={item.iri}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === highlightedIndex}
              className={`px-3 py-2 text-sm cursor-pointer text-slate-900 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 last:border-b-0 ${i === highlightedIndex ? "bg-slate-100 dark:bg-slate-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"}`}
              onClick={() => onSelect(item)}
            >
              <span className="font-medium">{item.label}</span>
              <span className="text-slate-500 dark:text-slate-400 ml-1">({item.shortForm})</span>
              {item.matchedSynonym && (
                <span className="block text-xs text-slate-500 dark:text-slate-400 truncate">
                  Synonym: {item.matchedSynonym}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {alreadyAddedLabel && (
        <p className="text-xs text-amber-700 dark:text-amber-400 mt-1" role="status">
          {alreadyAddedLabel} already added.
        </p>
      )}
      {showSelectFromListHint && (
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1" role="status">
          Select an option from the list when suggestions appear.
        </p>
      )}
    </div>
  );
}

interface UBERONSuggestion {
  iri: string;
  shortForm: string;
  uberonId: string;
  label: string;
  matchedSynonym?: string;
}

function TissueAutocomplete({
  label,
  placeholder,
  value,
  onChange,
  disabled,
  id,
  source = "ubergraph",
  required,
}: {
  label: string;
  placeholder: string;
  value: OntologyToken[];
  onChange: (tokens: OntologyToken[]) => void;
  disabled?: boolean;
  id: string;
  source?: "ubergraph" | "ols";
  required?: boolean;
}) {
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<UBERONSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [alreadyAddedLabel, setAlreadyAddedLabel] = useState<string | null>(null);
  const [showSelectFromListHint, setShowSelectFromListHint] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alreadyAddedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectFromListHintTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const DROPDOWN_MAX_H = 280;
  useEffect(() => {
    if (!open || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    setOpenUpward(spaceBelow < DROPDOWN_MAX_H);
  }, [open]);

  useEffect(() => {
    setHighlightedIndex(suggestions.length > 0 ? 0 : -1);
  }, [suggestions]);

  useEffect(() => {
    if (!alreadyAddedLabel) return;
    alreadyAddedTimeoutRef.current = setTimeout(() => setAlreadyAddedLabel(null), 2000);
    return () => {
      if (alreadyAddedTimeoutRef.current) clearTimeout(alreadyAddedTimeoutRef.current);
    };
  }, [alreadyAddedLabel]);

  useEffect(() => {
    if (!showSelectFromListHint) return;
    selectFromListHintTimeoutRef.current = setTimeout(() => setShowSelectFromListHint(false), 2500);
    return () => {
      if (selectFromListHintTimeoutRef.current) clearTimeout(selectFromListHintTimeoutRef.current);
    };
  }, [showSelectFromListHint]);

  const onSelect = useCallback(
    (item: UBERONSuggestion) => {
      const isDuplicate = value.some((t) => t.id === item.shortForm);
      setInput("");
      setSuggestions([]);
      setOpen(false);
      setHighlightedIndex(-1);
      if (isDuplicate) {
        setAlreadyAddedLabel(item.label);
        return;
      }
      onChange([...value, { id: item.shortForm, label: item.label }]);
    },
    [value, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        const trimmed = (e.target as HTMLInputElement).value?.trim() ?? "";
        if (trimmed && open && suggestions.length > 0 && highlightedIndex >= 0) {
          e.preventDefault();
          onSelect(suggestions[highlightedIndex]);
          return;
        }
        if (trimmed) {
          e.preventDefault();
          setShowSelectFromListHint(true);
          return;
        }
      }
      if (!open || suggestions.length === 0) {
        if (e.key === "Escape") setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
      } else if (e.key === "Enter" && highlightedIndex >= 0) {
        e.preventDefault();
        onSelect(suggestions[highlightedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setHighlightedIndex(-1);
      }
    },
    [open, suggestions, highlightedIndex, onSelect]
  );

  const fetchSuggestions = useCallback(
    async (q: string) => {
      if (q.length < 2) {
        setSuggestions([]);
        return;
      }
      setLoading(true);
      setOpen(true);
      try {
        const res = await fetch(
          `/api/tools/ontology/uberon/search?q=${encodeURIComponent(q)}&limit=15&source=${source}`
        );
      const data = await res.json();
      setSuggestions(data.results ?? []);
      setOpen(true);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  },
    [source]
  );

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!input.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(input.trim());
      debounceRef.current = null;
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [input, fetchSuggestions]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const remove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  return (
    <div ref={wrapperRef} className="space-y-1 relative">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {required && <sup className="text-red-600 dark:text-red-400 ml-0.5" aria-hidden>*</sup>}
      </label>
      <div className="flex flex-wrap gap-2 items-center rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1.5 min-h-[38px] focus-within:ring-2 focus-within:ring-niaid-header focus-within:border-transparent">
        {value.map((token, i) => (
          <span
            key={`${token.id}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-600 text-slate-800 dark:text-slate-200 text-sm"
          >
            {token.label}
            {!disabled && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="hover:text-red-600 dark:hover:text-red-400 font-medium leading-none"
                aria-label={`Remove ${token.label}`}
              >
                ×
              </button>
            )}
          </span>
        ))}
        <input
          id={id}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder={value.length === 0 ? placeholder : "Add tissue…"}
          disabled={disabled}
          className="flex-1 min-w-[120px] px-1 py-0.5 text-sm bg-transparent border-0 border-none outline-none text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-activedescendant={highlightedIndex >= 0 ? `${id}-option-${highlightedIndex}` : undefined}
          role="combobox"
          aria-label={label}
        />
      </div>
      {open && (suggestions.length > 0 || loading) && (
        <ul
          id={`${id}-listbox`}
          role="listbox"
          className={`absolute z-50 w-full max-h-60 overflow-auto rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg ${openUpward ? "bottom-full mb-0.5" : "mt-0.5"}`}
        >
          {loading && suggestions.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">Searching…</li>
          )}
          {suggestions.map((item, i) => (
            <li
              key={item.iri}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === highlightedIndex}
              className={`px-3 py-2 text-sm cursor-pointer text-slate-900 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 last:border-b-0 ${i === highlightedIndex ? "bg-slate-100 dark:bg-slate-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"}`}
              onClick={() => onSelect(item)}
            >
              <span className="font-medium">{item.label}</span>
              <span className="text-slate-500 dark:text-slate-400 ml-1">({item.shortForm})</span>
              {item.matchedSynonym && (
                <span className="block text-xs text-slate-500 dark:text-slate-400 truncate">
                  Synonym: {item.matchedSynonym}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {alreadyAddedLabel && (
        <p className="text-xs text-amber-700 dark:text-amber-400 mt-1" role="status">
          {alreadyAddedLabel} already added.
        </p>
      )}
      {showSelectFromListHint && (
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1" role="status">
          Select an option from the list when suggestions appear.
        </p>
      )}
    </div>
  );
}

interface EFOSuggestion {
  iri: string;
  shortForm: string;
  efoId: string;
  label: string;
  matchedSynonym?: string;
}

function EfoAutocomplete({
  label,
  placeholder,
  value,
  onChange,
  disabled,
  id,
  required,
}: {
  label: string;
  placeholder: string;
  value: OntologyToken[];
  onChange: (tokens: OntologyToken[]) => void;
  disabled?: boolean;
  id: string;
  required?: boolean;
}) {
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<EFOSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [alreadyAddedLabel, setAlreadyAddedLabel] = useState<string | null>(null);
  const [showSelectFromListHint, setShowSelectFromListHint] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alreadyAddedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectFromListHintTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const DROPDOWN_MAX_H = 280;
  useEffect(() => {
    if (!open || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    setOpenUpward(spaceBelow < DROPDOWN_MAX_H);
  }, [open]);

  useEffect(() => {
    setHighlightedIndex(suggestions.length > 0 ? 0 : -1);
  }, [suggestions]);

  useEffect(() => {
    if (!alreadyAddedLabel) return;
    alreadyAddedTimeoutRef.current = setTimeout(() => setAlreadyAddedLabel(null), 2000);
    return () => {
      if (alreadyAddedTimeoutRef.current) clearTimeout(alreadyAddedTimeoutRef.current);
    };
  }, [alreadyAddedLabel]);

  useEffect(() => {
    if (!showSelectFromListHint) return;
    selectFromListHintTimeoutRef.current = setTimeout(() => setShowSelectFromListHint(false), 2500);
    return () => {
      if (selectFromListHintTimeoutRef.current) clearTimeout(selectFromListHintTimeoutRef.current);
    };
  }, [showSelectFromListHint]);

  const onSelect = useCallback(
    (item: EFOSuggestion) => {
      const isDuplicate = value.some((t) => t.id === item.shortForm);
      setInput("");
      setSuggestions([]);
      setOpen(false);
      setHighlightedIndex(-1);
      if (isDuplicate) {
        setAlreadyAddedLabel(item.label);
        return;
      }
      onChange([...value, { id: item.shortForm, label: item.label }]);
    },
    [value, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        const trimmed = (e.target as HTMLInputElement).value?.trim() ?? "";
        if (trimmed && open && suggestions.length > 0 && highlightedIndex >= 0) {
          e.preventDefault();
          onSelect(suggestions[highlightedIndex]);
          return;
        }
        if (trimmed) {
          e.preventDefault();
          setShowSelectFromListHint(true);
          return;
        }
      }
      if (!open || suggestions.length === 0) {
        if (e.key === "Escape") setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
      } else if (e.key === "Enter" && highlightedIndex >= 0) {
        e.preventDefault();
        onSelect(suggestions[highlightedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setHighlightedIndex(-1);
      }
    },
    [open, suggestions, highlightedIndex, onSelect]
  );

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    setOpen(true);
    try {
      const res = await fetch(
        `/api/tools/ontology/efo/search?q=${encodeURIComponent(q)}&limit=15`
      );
      const data = await res.json();
      setSuggestions(data.results ?? []);
      setOpen(true);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!input.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(input.trim());
      debounceRef.current = null;
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [input, fetchSuggestions]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const remove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  return (
    <div ref={wrapperRef} className="space-y-1 relative">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {required && <sup className="text-red-600 dark:text-red-400 ml-0.5" aria-hidden>*</sup>}
      </label>
      <div className="flex flex-wrap gap-2 items-center rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1.5 min-h-[38px] focus-within:ring-2 focus-within:ring-niaid-header focus-within:border-transparent">
        {value.map((token, i) => (
          <span
            key={`${token.id}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-600 text-slate-800 dark:text-slate-200 text-sm"
          >
            {token.label}
            {!disabled && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="hover:text-red-600 dark:hover:text-red-400 font-medium leading-none"
                aria-label={`Remove ${token.label}`}
              >
                ×
              </button>
            )}
          </span>
        ))}
        <input
          id={id}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder={value.length === 0 ? placeholder : "Add disease…"}
          disabled={disabled}
          className="flex-1 min-w-[120px] px-1 py-0.5 text-sm bg-transparent border-0 border-none outline-none text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-activedescendant={highlightedIndex >= 0 ? `${id}-option-${highlightedIndex}` : undefined}
          role="combobox"
          aria-label={label}
        />
      </div>
      {open && (suggestions.length > 0 || loading) && (
        <ul
          id={`${id}-listbox`}
          role="listbox"
          className={`absolute z-50 w-full max-h-60 overflow-auto rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg ${openUpward ? "bottom-full mb-0.5" : "mt-0.5"}`}
        >
          {loading && suggestions.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">Searching…</li>
          )}
          {suggestions.map((item, i) => (
            <li
              key={item.iri}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === highlightedIndex}
              className={`px-3 py-2 text-sm cursor-pointer text-slate-900 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 last:border-b-0 ${i === highlightedIndex ? "bg-slate-100 dark:bg-slate-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"}`}
              onClick={() => onSelect(item)}
            >
              <span className="font-medium">{item.label}</span>
              <span className="text-slate-500 dark:text-slate-400 ml-1">({item.shortForm})</span>
              {item.matchedSynonym && (
                <span className="block text-xs text-slate-500 dark:text-slate-400 truncate">
                  Synonym: {item.matchedSynonym}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {alreadyAddedLabel && (
        <p className="text-xs text-amber-700 dark:text-amber-400 mt-1" role="status">
          {alreadyAddedLabel} already added.
        </p>
      )}
      {showSelectFromListHint && (
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1" role="status">
          Select an option from the list when suggestions appear.
        </p>
      )}
    </div>
  );
}

interface HGNCSuggestion {
  symbol: string;
  name: string;
  hgncId: string;
}

function GeneSymbolAutocomplete({
  label,
  placeholder,
  value,
  onChange,
  disabled,
  id,
  required,
  single = false,
}: {
  label: string;
  placeholder: string;
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
  id: string;
  required?: boolean;
  single?: boolean;
}) {
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<HGNCSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [alreadyAddedLabel, setAlreadyAddedLabel] = useState<string | null>(null);
  const [showSelectFromListHint, setShowSelectFromListHint] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alreadyAddedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectFromListHintTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const DROPDOWN_MAX_H = 280;
  useEffect(() => {
    if (!open || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    setOpenUpward(spaceBelow < DROPDOWN_MAX_H);
  }, [open]);

  useEffect(() => {
    setHighlightedIndex(suggestions.length > 0 ? 0 : -1);
  }, [suggestions]);

  useEffect(() => {
    if (!alreadyAddedLabel) return;
    alreadyAddedTimeoutRef.current = setTimeout(() => setAlreadyAddedLabel(null), 2000);
    return () => {
      if (alreadyAddedTimeoutRef.current) clearTimeout(alreadyAddedTimeoutRef.current);
    };
  }, [alreadyAddedLabel]);

  useEffect(() => {
    if (!showSelectFromListHint) return;
    selectFromListHintTimeoutRef.current = setTimeout(() => setShowSelectFromListHint(false), 2500);
    return () => {
      if (selectFromListHintTimeoutRef.current) clearTimeout(selectFromListHintTimeoutRef.current);
    };
  }, [showSelectFromListHint]);

  const onSelect = useCallback(
    (item: HGNCSuggestion) => {
      const isDuplicate = value.includes(item.symbol);
      setInput("");
      setSuggestions([]);
      setOpen(false);
      setHighlightedIndex(-1);
      if (isDuplicate) {
        setAlreadyAddedLabel(item.symbol);
        return;
      }
      if (single) {
        onChange([item.symbol]);
      } else {
        onChange([...value, item.symbol]);
      }
    },
    [value, onChange, single]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        const trimmed = (e.target as HTMLInputElement).value?.trim() ?? "";
        if (trimmed && isEnsemblGeneStableId(trimmed)) {
          e.preventDefault();
          const normalized = trimmed.toUpperCase();
          if (value.includes(normalized)) {
            setAlreadyAddedLabel(normalized);
            return;
          }
          if (single) {
            onChange([normalized]);
          } else {
            onChange([...value, normalized]);
          }
          setInput("");
          setSuggestions([]);
          setOpen(false);
          setHighlightedIndex(-1);
          return;
        }
        if (trimmed && open && suggestions.length > 0 && highlightedIndex >= 0) {
          e.preventDefault();
          onSelect(suggestions[highlightedIndex]);
          return;
        }
        if (trimmed) {
          e.preventDefault();
          setShowSelectFromListHint(true);
          return;
        }
      }
      if (!open || suggestions.length === 0) {
        if (e.key === "Escape") setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
      } else if (e.key === "Enter" && highlightedIndex >= 0) {
        e.preventDefault();
        onSelect(suggestions[highlightedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setHighlightedIndex(-1);
      }
    },
    [open, suggestions, highlightedIndex, onSelect, value, onChange, single]
  );

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    setOpen(true);
    try {
      const res = await fetch(
        `/api/tools/ontology/hgnc/search?q=${encodeURIComponent(q)}&limit=15`
      );
      const data = await res.json();
      setSuggestions(data.results ?? []);
      setOpen(true);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!input.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    if (isEnsemblGeneStableId(input.trim())) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(input.trim());
      debounceRef.current = null;
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [input, fetchSuggestions]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const remove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const displayValue = single ? value.slice(0, 1) : value;

  return (
    <div ref={wrapperRef} className="space-y-1 relative">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {required && <sup className="text-red-600 dark:text-red-400 ml-0.5" aria-hidden>*</sup>}
      </label>
      <div className="flex flex-wrap gap-2 items-center rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1.5 min-h-[38px] focus-within:ring-2 focus-within:ring-niaid-header focus-within:border-transparent">
        {displayValue.map((v, i) => (
          <span
            key={`${v}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-600 text-slate-800 dark:text-slate-200 text-sm"
          >
            {v}
            {!disabled && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="hover:text-red-600 dark:hover:text-red-400 font-medium leading-none"
                aria-label={`Remove ${v}`}
              >
                ×
              </button>
            )}
          </span>
        ))}
        <input
          id={id}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder={displayValue.length === 0 ? placeholder : single ? "" : "Add gene…"}
          disabled={disabled}
          className="flex-1 min-w-[120px] px-1 py-0.5 text-sm bg-transparent border-0 border-none outline-none text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-activedescendant={highlightedIndex >= 0 ? `${id}-option-${highlightedIndex}` : undefined}
          role="combobox"
          aria-label={label}
        />
      </div>
      {open && (suggestions.length > 0 || loading) && (
        <ul
          id={`${id}-listbox`}
          role="listbox"
          className={`absolute z-50 w-full max-h-60 overflow-auto rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg ${openUpward ? "bottom-full mb-0.5" : "mt-0.5"}`}
        >
          {loading && suggestions.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">Searching…</li>
          )}
          {suggestions.map((item, i) => (
            <li
              key={item.hgncId || item.symbol}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === highlightedIndex}
              className={`px-3 py-2 text-sm cursor-pointer text-slate-900 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 last:border-b-0 ${i === highlightedIndex ? "bg-slate-100 dark:bg-slate-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"}`}
              onClick={() => onSelect(item)}
            >
              <span className="font-medium">{item.symbol}</span>
              {item.name && item.name !== item.symbol && (
                <span className="text-slate-500 dark:text-slate-400 ml-1 truncate">{item.name}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {alreadyAddedLabel && (
        <p className="text-xs text-amber-700 dark:text-amber-400 mt-1" role="status">
          {alreadyAddedLabel} already added.
        </p>
      )}
      {showSelectFromListHint && (
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1" role="status">
          Select an option from the list when suggestions appear, or paste an Ensembl gene ID (e.g. ENSMUSG…) and press Enter.
        </p>
      )}
    </div>
  );
}

interface WikidataDrugSuggestion {
  label: string;
  wikidata_id: string;
  wikidata_iri?: string;
  description?: string;
}

const DRUG_DEBOUNCE_MS = 400;

function DrugAutocomplete({
  label,
  placeholder,
  value,
  onChange,
  disabled,
  id,
  required,
}: {
  label: string;
  placeholder: string;
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
  id: string;
  required?: boolean;
}) {
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<WikidataDrugSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [alreadyAddedLabel, setAlreadyAddedLabel] = useState<string | null>(null);
  const [showSelectFromListHint, setShowSelectFromListHint] = useState(false);
  const [openUpward, setOpenUpward] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alreadyAddedTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectFromListHintTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const DROPDOWN_MAX_H = 280;
  useEffect(() => {
    if (!open || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    setOpenUpward(spaceBelow < DROPDOWN_MAX_H);
  }, [open]);

  useEffect(() => {
    setHighlightedIndex(suggestions.length > 0 ? 0 : -1);
  }, [suggestions]);

  useEffect(() => {
    if (!alreadyAddedLabel) return;
    alreadyAddedTimeoutRef.current = setTimeout(() => setAlreadyAddedLabel(null), 2000);
    return () => {
      if (alreadyAddedTimeoutRef.current) clearTimeout(alreadyAddedTimeoutRef.current);
    };
  }, [alreadyAddedLabel]);

  useEffect(() => {
    if (!showSelectFromListHint) return;
    selectFromListHintTimeoutRef.current = setTimeout(() => setShowSelectFromListHint(false), 2500);
    return () => {
      if (selectFromListHintTimeoutRef.current) clearTimeout(selectFromListHintTimeoutRef.current);
    };
  }, [showSelectFromListHint]);

  const onSelect = useCallback(
    (item: WikidataDrugSuggestion) => {
      const isDuplicate = value.includes(item.label);
      setInput("");
      setSuggestions([]);
      setOpen(false);
      setHighlightedIndex(-1);
      if (isDuplicate) {
        setAlreadyAddedLabel(item.label);
        return;
      }
      onChange([...value, item.label]);
    },
    [value, onChange]
  );

  const removeDrug = useCallback(
    (index: number) => {
      onChange(value.filter((_, i) => i !== index));
    },
    [value, onChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        const trimmed = (e.target as HTMLInputElement).value?.trim() ?? "";
        if (trimmed && open && suggestions.length > 0 && highlightedIndex >= 0) {
          e.preventDefault();
          onSelect(suggestions[highlightedIndex]);
          return;
        }
        if (trimmed) {
          e.preventDefault();
          setShowSelectFromListHint(true);
          return;
        }
      }
      if (!open || suggestions.length === 0) {
        if (e.key === "Escape") setOpen(false);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlightedIndex((i) => (i < suggestions.length - 1 ? i + 1 : 0));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlightedIndex((i) => (i > 0 ? i - 1 : suggestions.length - 1));
      } else if (e.key === "Enter" && highlightedIndex >= 0) {
        e.preventDefault();
        onSelect(suggestions[highlightedIndex]);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        setHighlightedIndex(-1);
      }
    },
    [open, suggestions, highlightedIndex, onSelect]
  );

  const fetchSuggestions = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    setOpen(true);
    try {
      const res = await fetch(
        `/api/tools/ontology/wikidata/drugs?q=${encodeURIComponent(q)}&limit=15`
      );
      const data = await res.json();
      setSuggestions(data.results ?? []);
    } catch {
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!input.trim()) {
      setSuggestions([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      fetchSuggestions(input.trim());
      debounceRef.current = null;
    }, DRUG_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [input, fetchSuggestions]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={wrapperRef} className="space-y-1 relative">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
        {required && <sup className="text-red-600 dark:text-red-400 ml-0.5" aria-hidden>*</sup>}
      </label>
      <div className="flex flex-wrap gap-2 items-center rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1.5 min-h-[38px] focus-within:ring-2 focus-within:ring-niaid-header focus-within:border-transparent">
        {value.map((drug, i) => (
          <span
            key={`${drug}-${i}`}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-600 text-slate-800 dark:text-slate-200 text-sm"
          >
            {drug}
            {!disabled && (
              <button
                type="button"
                onClick={() => removeDrug(i)}
                className="hover:text-red-600 dark:hover:text-red-400 font-medium leading-none"
                aria-label={`Remove ${drug}`}
              >
                ×
              </button>
            )}
          </span>
        ))}
        <input
          id={id}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => suggestions.length > 0 && setOpen(true)}
          placeholder={value.length === 0 ? placeholder : "Add drug…"}
          disabled={disabled}
          className="flex-1 min-w-[120px] px-1 py-0.5 text-sm bg-transparent border-0 border-none outline-none text-slate-900 dark:text-slate-100 placeholder-slate-500 dark:placeholder-slate-400"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-listbox`}
          aria-activedescendant={highlightedIndex >= 0 ? `${id}-option-${highlightedIndex}` : undefined}
          role="combobox"
          aria-label={label}
          aria-required={required}
          aria-invalid={required && value.length === 0}
        />
      </div>
      {alreadyAddedLabel && (
        <p className="text-xs text-amber-700 dark:text-amber-400 mt-1" role="status">
          {alreadyAddedLabel} already added.
        </p>
      )}
      {open && (suggestions.length > 0 || loading) && (
        <ul
          id={`${id}-listbox`}
          role="listbox"
          className={`absolute z-50 w-full max-h-60 overflow-auto rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-lg ${openUpward ? "bottom-full mb-0.5" : "mt-0.5"}`}
        >
          {loading && suggestions.length === 0 && (
            <li className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">Searching Wikidata…</li>
          )}
          {suggestions.map((item, i) => (
            <li
              key={item.wikidata_id || item.label}
              id={`${id}-option-${i}`}
              role="option"
              aria-selected={i === highlightedIndex}
              className={`px-3 py-2 text-sm cursor-pointer text-slate-900 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 last:border-b-0 ${i === highlightedIndex ? "bg-slate-100 dark:bg-slate-700" : "hover:bg-slate-100 dark:hover:bg-slate-700"}`}
              onClick={() => onSelect(item)}
            >
              <span className="font-medium">{item.label}</span>
              {item.description && item.description !== item.label && (
                <span className="text-slate-500 dark:text-slate-400 ml-1 truncate block">{item.description}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {showSelectFromListHint && (
        <p className="text-xs text-slate-600 dark:text-slate-400 mt-1" role="status">
          Select an option from the list when suggestions appear.
        </p>
      )}
    </div>
  );
}

/** Human-readable labels and placeholders for known slot names. */
const SLOT_LABELS: Record<string, { label: string; placeholder: string }> = {
  q: { label: "Query (CURIE, URI, or label)", placeholder: "e.g. MONDO:0004979" },
  keywords: { label: "Keywords", placeholder: "e.g. influenza vaccine" },
  health_condition: {
    label: "Health condition",
    placeholder: "Search and pick from list (MONDO)",
  },
  health_conditions: { label: "Health conditions (MONDO IRIs)", placeholder: "e.g. MONDO:0005015 or diabetes" },
  species: { label: "Host species", placeholder: "Search and pick from list (NCBI Taxon)" },
  infectious_agent: {
    label: "Pathogen species",
    placeholder: "Search and pick from list (NCBI Taxon)",
  },
  drugs: { label: "Drugs", placeholder: "e.g. doxycycline" },
  drug: { label: "Drug name(s)", placeholder: "e.g. aspirin, Lipitor, tocilizumab" },
  gene_symbols: {
    label: "Gene symbol(s)",
    placeholder: "e.g. DUSP2, TP53 — or paste Ensembl gene ID (ENSMUSG…, ENSG…)",
  },
  gene_symbol: { label: "Gene symbol", placeholder: "e.g. DUSP2" },
  experiment_id: { label: "Experiment ID", placeholder: "e.g. E-GEOD-76" },
  organism_taxon_ids: { label: "Organism / taxon IDs", placeholder: "e.g. Mus musculus or 10090" },
  tissue_uberon_ids: { label: "Tissue (UBERON, Ubergraph)", placeholder: "e.g. heart or UBERON:0000948" },
  tissue_uberon_ids_ols: { label: "Tissue (UBERON)", placeholder: "e.g. heart or UBERON:0000948" },
  factor_terms: { label: "Factor terms", placeholder: "e.g. disease, treatment" },
  disease_efo_ids: { label: "Disease (EFO IDs)", placeholder: "e.g. EFO:0000408 or diabetes" },
  min_experiments: { label: "Min experiments", placeholder: "e.g. 2 or 3 (genes must appear in this many experiments)" },
  min_abs_log2fc: { label: "Min |log2FC|", placeholder: "e.g. 1 or 1.5" },
  max_adj_p_value: { label: "Max adj. p-value", placeholder: "e.g. 0.05" },
  limit: { label: "Limit", placeholder: "e.g. 50 or 100" },
  direction: { label: "Direction", placeholder: "up or down" },
  only_gene_expression: { label: "Only show datasets with gene expression data", placeholder: "" },
  mondo_expand_descendants: {
    label: "Include MONDO subclasses",
    placeholder: "",
  },
  max_results: { label: "Maximum results", placeholder: "Default 500" },
};

export function getSlotMeta(varName: string): { label: string; placeholder: string } {
  return (
    SLOT_LABELS[varName] ?? {
      label: varName.replace(/_/g, " "),
      placeholder: "",
    }
  );
}

/** Returns true if the value is considered filled for a required slot. */
export function isSlotFilled(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (typeof value === "string") return value.trim() !== "";
  if (Array.isArray(value)) return value.length > 0 && value.some((x) => String(x).trim() !== "");
  return false;
}

export interface SlotFormProps {
  template: TemplateDefinition;
  values: Record<string, string | string[]>;
  onChange: (values: Record<string, string | string[]>) => void;
  disabled?: boolean;
  /** Shown above primary slots (e.g. dataset search keywords). */
  primarySectionTitle?: string;
  /** Shown above the optional / advanced block; adds a top divider when set. */
  metadataSectionTitle?: string;
}

export function SlotForm({
  template,
  values,
  onChange,
  disabled,
  primarySectionTitle,
  metadataSectionTitle,
}: SlotFormProps) {
  const [advancedOpen, setAdvancedOpen] = useState(true);
  const required = template.required_slots ?? [];
  const optional = template.optional_slots ?? [];
  // dataset_search and geo_dataset_search use keywords as primary slot
  const primarySlots =
    required.length > 0
      ? required
      : template.id === "dataset_search" || template.id === "geo_dataset_search"
        ? ["keywords"]
        : [];

  const updateSlot = (key: string, value: string | string[]) => {
    onChange({ ...values, [key]: value });
  };

  const commitOntologyTokens = (idSlot: string, tokens: OntologyToken[]) => {
    const lk = ONTOLOGY_ID_TO_LABEL_SLOT[idSlot];
    if (!lk) {
      updateSlot(
        idSlot,
        tokens.map((t) => t.id)
      );
      return;
    }
    onChange({
      ...values,
      [idSlot]: tokens.map((t) => t.id),
      [lk]: tokens.map((t) => t.label),
    });
  };

  const renderInput = (slotName: string) => {
    const { label, placeholder } = getSlotMeta(slotName);
    const isRequired = required.includes(slotName);
    const raw = values[slotName];

    if (
      slotName === "health_condition" &&
      (template.id === "dataset_search" || template.id === "geo_dataset_search")
    ) {
      const mondoTokens = ontologyTokensFromValues(values, slotName);
      return (
        <MondoAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={mondoTokens}
          onChange={(t) => commitOntologyTokens(slotName, t)}
          disabled={disabled}
          required={isRequired}
        />
      );
    }
    if (
      (slotName === "species" || slotName === "infectious_agent") &&
      (template.id === "dataset_search" || template.id === "geo_dataset_search")
    ) {
      const organismTokens = ontologyTokensFromValues(values, slotName);
      return (
        <OrganismAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={organismTokens}
          onChange={(t) => commitOntologyTokens(slotName, t)}
          disabled={disabled}
          required={isRequired}
        />
      );
    }
    if (slotName === "organism_taxon_ids") {
      const organismTokens = ontologyTokensFromValues(values, slotName);
      return (
        <OrganismAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={organismTokens}
          onChange={(t) => commitOntologyTokens(slotName, t)}
          disabled={disabled}
          required={isRequired}
        />
      );
    }
    if (slotName === "tissue_uberon_ids") {
      const tissueTokens = ontologyTokensFromValues(values, slotName);
      return (
        <TissueAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={tissueTokens}
          onChange={(t) => commitOntologyTokens(slotName, t)}
          disabled={disabled}
          source="ubergraph"
          required={isRequired}
        />
      );
    }
    if (slotName === "tissue_uberon_ids_ols") {
      const tissueTokens = ontologyTokensFromValues(values, slotName);
      return (
        <TissueAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={tissueTokens}
          onChange={(t) => commitOntologyTokens(slotName, t)}
          disabled={disabled}
          source="ols"
          required={isRequired}
        />
      );
    }
    if (slotName === "gene_symbol") {
      const geneValue = Array.isArray(raw) ? raw : typeof raw === "string" ? (raw.trim() ? [raw.trim()] : []) : [];
      return (
        <GeneSymbolAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={geneValue}
          onChange={(v) => updateSlot(slotName, v[0] ?? "")}
          disabled={disabled}
          required={isRequired}
          single
        />
      );
    }
    if (slotName === "gene_symbols") {
      const geneValue = Array.isArray(raw) ? raw : typeof raw === "string" ? raw.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean) : [];
      return (
        <GeneSymbolAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={geneValue}
          onChange={(v) => updateSlot(slotName, v)}
          disabled={disabled}
          required={isRequired}
        />
      );
    }
    if (slotName === "disease_efo_ids") {
      const diseaseTokens = ontologyTokensFromValues(values, slotName);
      return (
        <EfoAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={diseaseTokens}
          onChange={(t) => commitOntologyTokens(slotName, t)}
          disabled={disabled}
          required={isRequired}
        />
      );
    }
    if (slotName === "drug") {
      const drugValue = Array.isArray(raw)
        ? raw.filter((x): x is string => typeof x === "string" && x.trim() !== "")
        : typeof raw === "string"
          ? raw.trim()
            ? [raw.trim()]
            : []
          : [];
      return (
        <DrugAutocomplete
          key={slotName}
          id={`slot-${template.id}-${slotName}`}
          label={label}
          placeholder={placeholder}
          value={drugValue}
          onChange={(v) => updateSlot(slotName, v)}
          disabled={disabled}
          required={isRequired}
        />
      );
    }
    if (slotName === "mondo_expand_descendants") {
      if (template.id !== "dataset_search" && template.id !== "geo_dataset_search") {
        return null;
      }
      const rawVal: unknown = Array.isArray(raw) ? raw[0] : raw;
      const checked =
        rawVal === true ||
        rawVal === 1 ||
        (typeof rawVal === "string" && ["true", "1", "yes", "on"].includes(rawVal.trim().toLowerCase()));
      return (
        <div key={slotName} className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <input
              id={`slot-${template.id}-${slotName}`}
              type="checkbox"
              checked={checked}
              onChange={(e) => updateSlot(slotName, e.target.checked ? "true" : "false")}
              disabled={disabled}
              className="h-4 w-4 rounded border-slate-300 dark:border-slate-600 text-niaid-header focus:ring-niaid-header"
            />
            <label
              htmlFor={`slot-${template.id}-${slotName}`}
              className="text-sm font-medium text-slate-700 dark:text-slate-300 cursor-pointer"
            >
              {label} (match selected MONDO and more specific MONDO terms)
            </label>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 pl-6 max-w-xl">
            Expansion is limited to {DEFAULT_MONDO_DESCENDANT_EXPAND_CAP} subclasses.
          </p>
        </div>
      );
    }
    if (slotName === "only_gene_expression") {
      const checked = raw === "true" || (Array.isArray(raw) && raw[0] === "true");
      const checkboxLabel =
        template.id === "dataset_search"
          ? "Only show datasets with GEO/GSE (gene expression) in metadata"
          : label;
      return (
        <div key={slotName} className="flex items-center gap-2">
          <input
            id={`slot-${template.id}-${slotName}`}
            type="checkbox"
            checked={checked}
            onChange={(e) => updateSlot(slotName, e.target.checked ? "true" : "false")}
            disabled={disabled}
            className="h-4 w-4 rounded border-slate-300 dark:border-slate-600 text-niaid-header focus:ring-niaid-header"
            aria-describedby={undefined}
          />
          <label htmlFor={`slot-${template.id}-${slotName}`} className="text-sm font-medium text-slate-700 dark:text-slate-300 cursor-pointer">
            {checkboxLabel}
          </label>
        </div>
      );
    }
    if (slotName === "max_results") {
      const rawStr = Array.isArray(raw) ? raw[0] : raw;
      const value = typeof rawStr === "string" && rawStr.trim() !== "" ? rawStr.trim() : "";
      const options = [
        { value: "", label: "Default (500)" },
        { value: "50", label: "50" },
        { value: "100", label: "100" },
        { value: "200", label: "200" },
        { value: "500", label: "500" },
      ];
      return (
        <div key={slotName} className="space-y-1">
          <label htmlFor={`slot-${template.id}-${slotName}`} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {label}
          </label>
          <select
            id={`slot-${template.id}-${slotName}`}
            value={value}
            onChange={(e) => updateSlot(slotName, e.target.value)}
            disabled={disabled}
            className="block w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm focus:border-niaid-header focus:ring-1 focus:ring-niaid-header sm:text-sm"
          >
            {options.map((opt) => (
              <option key={opt.value || "default"} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      );
    }
    if (slotName === "direction") {
      const rawStr = Array.isArray(raw) ? raw[0] : raw;
      const value = typeof rawStr === "string" ? rawStr.trim().toLowerCase() : "";
      const options = [
        { value: "", label: "Either (up or down)" },
        { value: "up", label: "Up (upregulated)" },
        { value: "down", label: "Down (downregulated)" },
      ];
      return (
        <div key={slotName} className="space-y-1">
          <label htmlFor={`slot-${template.id}-${slotName}`} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            {label}
          </label>
          <select
            id={`slot-${template.id}-${slotName}`}
            value={value === "up" || value === "down" ? value : ""}
            onChange={(e) => updateSlot(slotName, e.target.value)}
            disabled={disabled}
            className="block w-full rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm focus:border-niaid-header focus:ring-1 focus:ring-niaid-header sm:text-sm"
          >
            {options.map((opt) => (
              <option key={opt.value || "either"} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      );
    }
    const value = Array.isArray(raw) ? raw.join(", ") : (raw ?? "");

    return (
      <div key={slotName} className="space-y-1">
        <label htmlFor={`slot-${template.id}-${slotName}`} className="block text-sm font-medium text-slate-700 dark:text-slate-300">
          {label}
          {isRequired && <sup className="text-red-600 dark:text-red-400 ml-0.5" aria-hidden>*</sup>}
        </label>
        <input
          id={`slot-${template.id}-${slotName}`}
          type="text"
          value={value}
          onChange={(e) => updateSlot(slotName, e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-niaid-header focus:border-transparent"
          aria-required={isRequired}
          aria-invalid={isRequired && !isSlotFilled(raw)}
        />
      </div>
    );
  };

  const filtersToggle = (
    <>
      <button
        type="button"
        onClick={() => setAdvancedOpen((o) => !o)}
        className="text-sm text-niaid-link hover:underline"
        aria-expanded={advancedOpen}
      >
        {advancedOpen ? "Hide filters" : "Filters / Advanced"}
      </button>
      {advancedOpen && (
        <div className="space-y-3 pl-0 border-l-0">
          {optional.map(renderInput)}
        </div>
      )}
    </>
  );

  return (
    <div className="space-y-3">
      {primarySectionTitle ? (
        <div className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {primarySectionTitle}
          </h2>
          {primarySlots.map(renderInput)}
        </div>
      ) : (
        primarySlots.map(renderInput)
      )}
      {optional.length > 0 &&
        (metadataSectionTitle ? (
          <div className="pt-4 mt-1 border-t border-slate-200 dark:border-slate-700 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {metadataSectionTitle}
            </h2>
            {filtersToggle}
          </div>
        ) : (
          filtersToggle
        ))}
    </div>
  );
}
