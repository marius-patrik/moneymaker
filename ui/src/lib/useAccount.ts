import { useCallback, useEffect, useState } from "react";

const KEY = "mm.account";
export const ALL_ACCOUNTS = "__all__";

/**
 * The account everything acts on.
 *
 * One selection in the header rather than a copy in every widget — a ticket
 * with its own selector could place an order against an account the header
 * was not showing.
 */
export function useAccount() {
  const [accountId, setState] = useState<string>(
    () => localStorage.getItem(KEY) ?? ALL_ACCOUNTS);

  // Other components mounted at the same time need to see the change too.
  useEffect(() => {
    const onChange = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      if (detail) setState(detail);
    };
    window.addEventListener("mm:account", onChange);
    return () => window.removeEventListener("mm:account", onChange);
  }, []);

  const setAccountId = useCallback((id: string) => {
    localStorage.setItem(KEY, id);
    setState(id);
    window.dispatchEvent(new CustomEvent("mm:account", { detail: id }));
  }, []);

  return {
    accountId,
    setAccountId,
    isAll: accountId === ALL_ACCOUNTS,
    /** Undefined when "all" — endpoints treat that as unscoped. */
    scoped: accountId === ALL_ACCOUNTS ? undefined : accountId,
  };
}
