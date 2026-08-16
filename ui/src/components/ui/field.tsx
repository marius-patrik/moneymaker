import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/**
 * A labelled input with the label programmatically bound to it.
 *
 * Writing <Label>Ticker</Label><Input/> looks right but leaves the two
 * unconnected: screen readers announce an unlabelled textbox, and clicking
 * the label doesn't focus the field. useId() gives each pair a unique id so
 * the association holds even with several Fields of the same name on screen.
 */
export interface FieldProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange"> {
  label: string;
  value: string;
  onValueChange: (v: string) => void;
  mono?: boolean;
  hint?: string;
  labelClassName?: string;
}

export const Field = React.forwardRef<HTMLInputElement, FieldProps>(
  ({ label, value, onValueChange, mono, hint, className, labelClassName, ...props }, ref) => {
    const id = React.useId();
    // An empty label renders a <label> that announces nothing — which passes
    // a naive "is it labelled" check while failing the actual purpose.
    if (process.env.NODE_ENV !== "production" && !label.trim()) {
      console.warn("Field rendered with an empty label", props);
    }
    const hintId = hint ? `${id}-hint` : undefined;
    return (
      <div className="space-y-1">
        <Label htmlFor={id} className={cn("text-xs", labelClassName)}>
          {label}
        </Label>
        <Input
          id={id}
          ref={ref}
          value={value}
          onChange={(e) => onValueChange(e.target.value)}
          aria-describedby={hintId}
          className={cn("h-8 text-sm", mono && "font-mono text-xs", className)}
          {...props}
        />
        {hint && (
          <p id={hintId} className="text-[11px] text-muted-foreground">
            {hint}
          </p>
        )}
      </div>
    );
  }
);
Field.displayName = "Field";
