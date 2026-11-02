import { useCallback, useRef, useState, type Dispatch, type SetStateAction } from "react";

// Text stays in this tab's session; File objects stay in memory across navigation.
const memory = new Map<string, unknown>();
export function useDraftState<T>(name: string, initial: T, persist = true): [T, Dispatch<SetStateAction<T>>] {
  const storageKey = "virallab-form-v1:" + name;
  const [value, update] = useState<T>(() => {
    if (memory.has(storageKey)) return memory.get(storageKey) as T;
    if (persist) {
      try {
        const raw = sessionStorage.getItem(storageKey);
        if (raw !== null) {
          const saved = JSON.parse(raw);
          if (typeof saved === typeof initial && Array.isArray(saved) === Array.isArray(initial)) return saved;
        }
      } catch { /* Storage can be unavailable; navigation still uses memory. */ }
    }
    return initial;
  });
  const current = useRef(value);
  const setValue = useCallback<Dispatch<SetStateAction<T>>>((next) => {
    const result = typeof next === "function" ? (next as (previous: T) => T)(current.current) : next;
    current.current = result;
    memory.set(storageKey, result);
    if (persist) {
      try { sessionStorage.setItem(storageKey, JSON.stringify(result)); } catch { /* Keep the memory draft. */ }
    }
    update(result);
  }, [storageKey, persist]);
  return [value, setValue];
}
