import { useEffect, useState } from "react";
import { api, type AppConfig } from "@/lib/api";

/**
 * Bottom status strip: what the app is connected to and where it stores
 * things. Ambient information a terminal keeps visible rather than burying
 * in a settings dialog.
 */
export function StatusBar() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    const ping = () =>
      api.config.get().then((c) => { setConfig(c); setOnline(true); })
        .catch(() => setOnline(false));
    ping();
    const t = setInterval(ping, 20000);
    return () => clearInterval(t);
  }, []);

  return (
    <footer className="flex h-6 shrink-0 items-center gap-3 border-t bg-muted/30 px-3 font-mono text-[10px] text-muted-foreground sm:px-4">
      <span className="flex items-center gap-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${online ? "bg-profit" : "bg-loss"}`} />
        {online ? "connected" : "offline"}
      </span>
      <span className="hidden sm:inline">·</span>
      <span className="hidden truncate sm:inline">{config?.home ?? ""}</span>
      <span className="ml-auto shrink-0">v{config?.version ?? "—"}</span>
    </footer>
  );
}
