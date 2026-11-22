import { useRef, useState } from "react";
import { ApprovalCard } from "@/components/ApprovalCard";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import type { CardRow } from "@/lib/api";

/** A quoted call cart opens on Home. Closing the sheet leaves the approval card on Home. */
export function CallCartReview({ cards }: { cards: CardRow[] }) {
  const [dismissed, setDismissed] = useState<string[]>(() => {
    try {
      const ids = JSON.parse(sessionStorage.getItem("pathya_dismissed_call_carts") || "[]");
      return Array.isArray(ids) ? ids.filter(id => typeof id === "string") : [];
    }
    catch { return []; }
  });
  const title = useRef<HTMLHeadingElement>(null);
  const row = cards.find(({ id, card, status }) => status === "waiting" && card.kind === "order" &&
    card.payload.ref && card.total && card.address && card.lines.length && !dismissed.includes(id));
  if (!row) return null;
  const dismiss = () => {
    const ids = [...dismissed.filter(id => cards.some(card => card.id === id)), row.id];
    setDismissed(ids);
    try { sessionStorage.setItem("pathya_dismissed_call_carts", JSON.stringify(ids)); } catch { /* in-memory dismissal still works */ }
  };
  return (
    <Dialog key={row.id} open onOpenChange={open => { if (!open) dismiss(); }}>
      <DialogContent aria-describedby={undefined} className="max-h-[90dvh] overflow-y-auto rounded-2xl p-4"
                     onOpenAutoFocus={event => { event.preventDefault(); title.current?.focus(); }}>
        <DialogTitle ref={title} tabIndex={-1} className="pr-8 outline-none">Review your grocery cart</DialogTitle>
        <ApprovalCard key={row.id} row={row} />
      </DialogContent>
    </Dialog>
  );
}
