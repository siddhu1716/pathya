import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, LocateFixed, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "@/components/ui/drawer";
import { api, Member, ringIn } from "@/lib/api";
import { cn } from "@/lib/utils";

const field = "w-full rounded-xl border bg-white/[0.03] px-3 py-2.5 text-[15px] outline-none focus:border-white/30";

/** Order a member's medicines: Pathya finds pharmacies near you and, after your tap, phones one to check stock, the
 * total and home delivery. Or open a pharmacy app yourself. */
export function PharmacySheet({ m, open, onClose }: { m: Member; open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  // Lines still to be checked against the paper are never read to a pharmacy.
  const [picked, setPicked] = useState<number[]>(() => m.meds.flatMap((x, i) => (x.unclear ? [] : [i])));
  const [area, setArea] = useState("");
  const [locating, setLocating] = useState(false);
  const [denied, setDenied] = useState(false);
  const { data: links } = useQuery({ queryKey: ["pharmacy-links", m.key], queryFn: () => api.pharmacyLinks(m.key), enabled: open });
  const find = useMutation({
    mutationFn: (where: { lat?: number; lng?: number; area?: string }) =>
      api.findPharmacy({ who: m.key, meds: picked, ...where, ...(ringIn() === "browser" ? { via: "browser" } : {}) }),
    onSuccess: () => {
      toast.success("Searching for pharmacies near you. A card appears on Home in about a minute.");
      qc.invalidateQueries({ queryKey: ["state"] });
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const busy = locating || find.isPending;

  const nearMe = () => {
    if (!navigator.geolocation) { setDenied(true); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (p) => { setLocating(false); find.mutate({ lat: p.coords.latitude, lng: p.coords.longitude, area: area.trim() }); },
      () => { setLocating(false); setDenied(true); toast.error("Location is off. Type the area instead."); },
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 10 * 60 * 1000 },
    );
  };

  return (
    <Drawer open={open} onOpenChange={(o) => !o && onClose()}>
      <DrawerContent className="bg-card border-t max-h-[92dvh]">
        <div className="p-4 pb-8 space-y-5 overflow-y-auto">
          <DrawerHeader className="px-0 text-left">
            <DrawerTitle className="font-medium">Order {m.key === "me" ? "my" : `${m.name}'s`} medicines</DrawerTitle>
            <DrawerDescription>
              Pathya finds pharmacies near you. After your tap it phones one to ask if they have these exactly as written, the total
              and home delivery. It never orders or accepts a substitute: you confirm on WhatsApp with the prescription.
            </DrawerDescription>
          </DrawerHeader>

          <div className="space-y-2">
            <h3 className="label px-1">Medicines, as written</h3>
            <div className="rounded-2xl border divide-y">
              {m.meds.map((x, i) => (
                <label key={i} className={cn("flex items-center gap-3 px-4 py-3", x.unclear && "opacity-50")}>
                  <input type="checkbox" className="w-4 h-4 accent-current" checked={picked.includes(i)} disabled={!!x.unclear}
                         onChange={() => setPicked(picked.includes(i) ? picked.filter((p) => p !== i) : [...picked, i])} />
                  <span className="min-w-0">
                    <span className="block text-[15px] truncate">{x.name_as_written}</span>
                    {x.unclear && <span className="block text-[12px] text-warning">Check it against the paper first</span>}
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Button className="w-full h-12" disabled={busy || !picked.length} onClick={nearMe}>
              {busy ? <Loader2 className="animate-spin" /> : <LocateFixed />} {locating ? "Getting your location" : find.isPending ? "Searching" : "Find pharmacies near me"}
            </Button>
            <p className="text-[12px] text-muted-foreground px-1">Your phone asks once to share your location. It is used only for this search.</p>
            <form className={cn("flex gap-2", !denied && "opacity-90")} onSubmit={(e) => { e.preventDefault(); if (area.trim()) find.mutate({ area: area.trim() }); }}>
              <input className={field} value={area} onChange={(e) => setArea(e.target.value)} placeholder="Or type the area: Madhapur, Kukatpally…" />
              <Button type="submit" variant="outline" size="icon" className="h-[46px] w-[46px] shrink-0" disabled={busy || !area.trim() || !picked.length} aria-label="Search this area">
                <Search className="w-4 h-4" />
              </Button>
            </form>
          </div>

          {!!links?.length && (
            <div className="space-y-2">
              <h3 className="label px-1">Or order yourself</h3>
              <div className="rounded-2xl border divide-y">
                {links.filter((l) => picked.some((i) => m.meds[i]?.name_as_written === l.name)).map((l) => (
                  <div key={l.name} className="px-4 py-3 space-y-1.5">
                    <p className="text-[14px] truncate">{l.name}</p>
                    <div className="flex gap-2">
                      {Object.entries(l.links).map(([site, url]) => (
                        <a key={site} href={url} target="_blank" rel="noreferrer" className="h-8 px-3 rounded-full border text-[12px] flex items-center text-muted-foreground">{site}</a>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-[12px] text-muted-foreground px-1">Opens each app's own search. Pathya does not fetch or compare prices.</p>
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
