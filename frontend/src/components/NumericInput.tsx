import * as React from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface NumericInputProps extends Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "type" | "value" | "onChange"
> {
  value: number | undefined;
  onChange: (value: number | undefined) => void;
  min?: number;
  max?: number;
  defaultValue?: number;
  /** "int" for integers, "float" for decimals */
  numericType?: "int" | "float";
  /** When true, allows empty input and calls onChange(undefined) on blur */
  allowEmpty?: boolean;
}

/**
 * Numeric input that validates only on blur. During typing, raw input is shown
 * so users can type "20" without the "2" being clamped to min before "0" is entered.
 */
const NumericInput = React.forwardRef<HTMLInputElement, NumericInputProps>(
  (
    {
      value,
      onChange,
      min,
      max,
      defaultValue = 0,
      numericType = "int",
      allowEmpty = false,
      className,
      onBlur,
      onFocus,
      ...props
    },
    ref
  ) => {
    const [localValue, setLocalValue] = React.useState<string | null>(null);
    const isEditing = localValue !== null;

    const displayValue = isEditing ? localValue : value === undefined ? "" : String(value);

    const parse = (s: string): number | undefined => {
      const trimmed = s.trim();
      if (trimmed === "") return allowEmpty ? undefined : defaultValue;
      const parsed = numericType === "float" ? parseFloat(trimmed) : parseInt(trimmed, 10);
      return isNaN(parsed) ? (allowEmpty ? undefined : defaultValue) : parsed;
    };

    const clamp = (n: number): number => {
      let result = n;
      if (min !== undefined) result = Math.max(min, result);
      if (max !== undefined) result = Math.min(max, result);
      return result;
    };

    const commit = () => {
      const parsed = parse(displayValue);
      if (parsed === undefined) {
        onChange(allowEmpty ? undefined : defaultValue);
      } else {
        onChange(clamp(parsed));
      }
      setLocalValue(null);
    };

    return (
      <Input
        ref={ref}
        type="text"
        inputMode="numeric"
        className={cn(className)}
        value={displayValue}
        onChange={(e) => {
          setLocalValue(e.target.value);
        }}
        onFocus={(e) => {
          setLocalValue(value === undefined ? "" : String(value));
          onFocus?.(e);
        }}
        onBlur={(e) => {
          commit();
          onBlur?.(e);
        }}
        {...props}
      />
    );
  }
);
NumericInput.displayName = "NumericInput";

export { NumericInput };
