import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

/** Indikator naik/turun/tetap — dipakai di mana pun ada perubahan periode. */
export function Delta({ value, suffix = "" }: { value: number; suffix?: string }) {
  const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : Minus;
  const cls = value > 0 ? "up" : value < 0 ? "down" : "flat";
  return (
    <span className={"delta " + cls}>
      <Icon size={13} strokeWidth={2.5} />
      {value > 0 ? "+" : ""}
      {value}
      {suffix}
    </span>
  );
}
