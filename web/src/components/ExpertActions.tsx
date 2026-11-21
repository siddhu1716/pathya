import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileImage, Loader2, PhoneOutgoing, ShoppingCart, Sparkles, Stethoscope } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, AppState } from "@/lib/api";

const day = (offset: number) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
};

const field = "w-full rounded-md border border-input bg-background px-3 py-2 text-sm";

export function AskBox({ swiggy }: { swiggy: boolean }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [reply, setReply] = useState("");
  const done = () => qc.invalidateQueries({ queryKey: ["state"] });

  const ask = useMutation({
    mutationFn: () => api.ask(text),
    onSuccess: (r) => {
      setReply(r.reply);
      setText("");
      done();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const cart = useMutation({
    mutationFn: () => api.planCart(text),
    onSuccess: () => {
      toast.success("Cart ready. Check the card below.");
      setText("");
      done();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const busy = ask.isPending || cart.isPending;

  return (
    <Card className="slide-up">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-primary" /> Ask QuickPick
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim()) ask.mutate();
          }}
        >
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={'"2 litres paalu, perugu, kottimeera" or "Book Amma\'s BP review this week, mornings"'}
            disabled={busy}
          />
          <div className="flex gap-2">
            <Button type="submit" disabled={busy || !text.trim()} className="flex-1">
              {ask.isPending ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
              Ask
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy || !text.trim() || !swiggy}
              onClick={() => cart.mutate()}
              title={swiggy ? "Build a Swiggy Instamart cart from this list" : "Swiggy is not connected"}
            >
              {cart.isPending ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <ShoppingCart className="w-4 h-4 mr-1" />}
              Cart from list
            </Button>
          </div>
        </form>
        {busy && <p className="text-sm text-muted-foreground">The Expert is working. Building a cart takes about 30 seconds.</p>}
        {reply && <p className="rounded-md bg-muted/60 px-3 py-2 text-sm whitespace-pre-line">{reply}</p>}
      </CardContent>
    </Card>
  );
}

export function ExpertActions({ state }: { state: AppState }) {
  const qc = useQueryClient();
  const done = (msg: string) => {
    toast.success(msg);
    qc.invalidateQueries({ queryKey: ["state"] });
  };
  const fail = (e: Error) => toast.error(e.message);

  const [book, setBook] = useState({
    patient: state.people.find((p) => p.role !== "cook")?.key ?? state.people[0]?.key ?? "",
    clinic: state.clinics[0]?.key ?? "",
    from: day(1),
    to: day(5),
    part: "morning",
    reason: "BP review",
  });
  const [rxPatient, setRxPatient] = useState(book.patient);
  const [photo, setPhoto] = useState<File | null>(null);

  const callList = useMutation({ mutationFn: api.callForList, onSuccess: () => done("Calling for the list"), onError: fail });
  const checkin = useMutation({ mutationFn: (p: string) => api.checkin(p), onSuccess: () => done("Check-in call started"), onError: fail });
  const booking = useMutation({
    mutationFn: () =>
      api.book({
        patient: book.patient,
        clinic: book.clinic,
        window_start: `${book.from}T00:00`,
        window_end: `${book.to}T23:59`,
        part: book.part,
        reason: book.reason,
      }),
    onSuccess: () => done("Calling the clinic"),
    onError: fail,
  });
  const rx = useMutation({
    mutationFn: () => api.prescription(rxPatient, photo as File),
    onSuccess: () => {
      setPhoto(null);
      done("Prescription read. Check the card and confirm.");
    },
    onError: fail,
  });

  return (
    <Card>
      <CardContent className="pt-6">
        <Tabs defaultValue="kitchen">
          <TabsList className="grid grid-cols-2 w-full">
            <TabsTrigger value="kitchen"><ShoppingCart className="w-4 h-4 mr-1" /> Kitchen</TabsTrigger>
            <TabsTrigger value="health"><Stethoscope className="w-4 h-4 mr-1" /> Health</TabsTrigger>
          </TabsList>

          <TabsContent value="kitchen" className="space-y-2 pt-2">
            <p className="text-sm text-muted-foreground">Phone someone at home for this week's grocery list. Their answer becomes a Swiggy cart card.</p>
            {state.people.map((p) => (
              <Button key={p.key} variant="outline" className="w-full justify-start" disabled={callList.isPending}
                      onClick={() => callList.mutate(p.key)}>
                <PhoneOutgoing className="w-4 h-4 mr-2" /> Call {p.name} for the list
                {p.language && <span className="ml-auto text-xs text-muted-foreground">{p.language}</span>}
              </Button>
            ))}
          </TabsContent>

          <TabsContent value="health" className="space-y-4 pt-2 text-sm">
            <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); booking.mutate(); }}>
              <p className="font-medium">Book a doctor by phone (only inside this window)</p>
              <div className="grid grid-cols-2 gap-2">
                <select className={field} value={book.patient} onChange={(e) => setBook({ ...book, patient: e.target.value })}>
                  {state.people.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
                </select>
                <select className={field} value={book.clinic} onChange={(e) => setBook({ ...book, clinic: e.target.value })}>
                  {state.clinics.map((c) => <option key={c.key} value={c.key}>{c.doctor}</option>)}
                </select>
                <input className={field} type="date" value={book.from} onChange={(e) => setBook({ ...book, from: e.target.value })} />
                <input className={field} type="date" value={book.to} onChange={(e) => setBook({ ...book, to: e.target.value })} />
                <select className={field} value={book.part} onChange={(e) => setBook({ ...book, part: e.target.value })}>
                  {["morning", "afternoon", "evening", "any"].map((p) => <option key={p}>{p}</option>)}
                </select>
                <input className={field} value={book.reason} placeholder="Reason" onChange={(e) => setBook({ ...book, reason: e.target.value })} />
              </div>
              <Button type="submit" className="w-full" disabled={booking.isPending || !book.reason}>
                <PhoneOutgoing className="w-4 h-4 mr-2" /> Phone the clinic
              </Button>
            </form>

            <div className="space-y-2">
              <p className="font-medium">Check-in call</p>
              {state.people.filter((p) => p.role !== "cook").map((p) => (
                <Button key={p.key} variant="outline" className="w-full justify-start" disabled={checkin.isPending}
                        onClick={() => checkin.mutate(p.key)}>
                  <PhoneOutgoing className="w-4 h-4 mr-2" /> Check in with {p.name}
                </Button>
              ))}
            </div>

            <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); if (photo) rx.mutate(); }}>
              <p className="font-medium">Prescription photo</p>
              <div className="grid grid-cols-2 gap-2">
                <select className={field} value={rxPatient} onChange={(e) => setRxPatient(e.target.value)}>
                  {state.people.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
                </select>
                <input className={field} type="file" accept="image/*" capture="environment"
                       onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
              </div>
              <Button type="submit" variant="outline" className="w-full" disabled={!photo || rx.isPending}>
                {rx.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FileImage className="w-4 h-4 mr-2" />}
                Read prescription
              </Button>
            </form>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
