import { useState } from "react";
import { Plus, Code, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Label } from "@/components/ui/label";
import { AnimatedIcon } from "@/components/ui/animated-icon";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

export function NewStrategyDialog({
  onCreated, compact = false,
}: { onCreated: () => void; compact?: boolean }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [source, setSource] = useState("");
  const [saving, setSaving] = useState(false);

  async function create() {
    setSaving(true);
    try {
      await api.strategies.create({ name, source: source.trim() || undefined });
      toast(`Created ${name}`, "success");
      setOpen(false); setName(""); setSource("");
      onCreated();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not create system", "error");
    }
    setSaving(false);
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {compact ? (
          <button aria-label="New system"
                  className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
            <AnimatedIcon icon={Plus} motionType="pop" className="h-3.5 w-3.5" />
          </button>
        ) : (
          <Button size="sm">
            <AnimatedIcon icon={Plus} motionType="pop" className="h-4 w-4" />
            New system
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New system</DialogTitle>
          <DialogDescription>
            Saved to your data directory and loaded immediately. Leave the code
            empty to start from a working template.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Name" value={name} mono placeholder="my_system"
                 onValueChange={setName} className="h-10"
                 hint="Lowercase with underscores — becomes the file name and the system id." />
          <div className="space-y-1">
            <Label htmlFor="new-src" className="text-xs">Code (optional)</Label>
            <textarea id="new-src" value={source} onChange={(e) => setSource(e.target.value)}
                      placeholder="Leave empty to use the template…" spellCheck={false} rows={12}
                      className="w-full rounded-lg border bg-background p-3 font-mono text-xs
                                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </div>
          <Button className="w-full" onClick={create} disabled={saving || !name}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Code className="h-4 w-4" />}
            Create system
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
