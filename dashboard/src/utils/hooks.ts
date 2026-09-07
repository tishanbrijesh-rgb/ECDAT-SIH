// Shared data-fetching and UI hooks.

import { useEffect, useState, useCallback, useRef } from "react";

type FetchState<T> = {
  data: T | null;
  loading: boolean;
  error: string;
};

/** Generic async data-fetch hook with abort support and retry. */
export function useFetch<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
): FetchState<T> & { refetch: () => void } {
  const [state, setState] = useState<FetchState<T>>({ data: null, loading: true, error: "" });
  const abortRef = useRef<AbortController | null>(null);

  const refetch = useCallback(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    fetcher(controller.signal)
      .then((data) => {
        setState({ data, loading: false, error: "" });
      })
      .catch((e) => {
        if ((e as Error)?.name === "AbortError") return;
        setState((prev) => ({ ...prev, loading: false, error: String(e) }));
      });
  }, [fetcher, ...deps]);

  useEffect(() => {
    refetch();
    return () => abortRef.current?.abort();
  }, deps);

  return { ...state, refetch };
}

/** Warns the user via beforeunload when they have unsaved changes. */
export function useDirtyGuard(isDirty: boolean): void {
  useEffect(() => {
    if (!isDirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);
}
