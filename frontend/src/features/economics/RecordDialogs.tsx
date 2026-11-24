import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select } from "@/components/ui/input";
import {
  EXPENSE_CATEGORIES, economicsApi, type Expense, type ExpenseInput, type HarvestInput, type HarvestSale, CATEGORY_LABEL,
} from "@/services/api/economics";  // prettier-ignore
import { errorMessage, formatDate, todayIso } from "@/utils/format";



const MONEY = /^\d{1,12}(\.\d{1,2})?$/;

function useSave<T>(cycleId: string, fn: (v: T) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ["economics", cycleId] }) });
}

function trigger(edit: string | undefined, label: string) {
  return edit ? (
    <Button variant="ghost" size="sm" aria-label={edit}><Pencil aria-hidden /><span className="md:sr-only">Edit</span></Button>
  ) : (
    <Button variant="secondary"><Plus aria-hidden />{label}</Button>
  );
}

export function ExpenseDialog({ cycleId, initial }: { cycleId: string; initial?: Expense }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = useSave(cycleId, (b: Omit<ExpenseInput, "crop_cycle_id">) =>
    initial ? economicsApi.updateExpense(initial.id, b) : economicsApi.addExpense({ ...b, crop_cycle_id: cycleId }));
  const title = initial ? `Edit expense of ${formatDate(initial.incurred_on)}` : "Add an expense";

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const amount = String(fd.get("amount_pkr") ?? "").trim();
    if (!MONEY.test(amount) || Number(amount) <= 0) {
      setError("Enter the amount in rupees, greater than 0, with at most 2 decimals.");
      return;
    }
    const note = String(fd.get("note") ?? "").trim();
    setError(null);
    save.mutate(
      { category: String(fd.get("category")) as ExpenseInput["category"], amount_pkr: amount, incurred_on: String(fd.get("incurred_on")), note: note || null },
      { onSuccess: () => setOpen(false), onError: (err) => setError(errorMessage(err)) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); setError(null); }}>
      <DialogTrigger asChild>{trigger(initial ? title : undefined, "Add expense")}</DialogTrigger>
      <DialogContent title={title} description="Amounts in Pakistani rupees (PKR).">
        <form onSubmit={submit} className="grid gap-3" noValidate>
          <FormField label="Category">
            <Select name="category" defaultValue={initial?.category ?? "seed"}>
              {EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
            </Select>
          </FormField>
          <FormField label="Amount (PKR)"><Input name="amount_pkr" inputMode="decimal" defaultValue={initial?.amount_pkr ?? ""} /></FormField>
          <FormField label="Date"><Input name="incurred_on" type="date" max={todayIso()} required defaultValue={initial?.incurred_on ?? todayIso()} /></FormField>
          <FormField label="Note" optional><Input name="note" maxLength={300} defaultValue={initial?.note ?? ""} /></FormField>
          {error && <InlineError message={error} />}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={save.isPending}>{save.isPending ? "Savingâ€¦" : "Save expense"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function HarvestDialog({ cycleId, initial }: { cycleId: string; initial?: HarvestSale }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = useSave(cycleId, (b: Omit<HarvestInput, "crop_cycle_id">) =>
    initial ? economicsApi.updateHarvest(initial.id, b) : economicsApi.addHarvest({ ...b, crop_cycle_id: cycleId }));
  const title = initial ? `Edit harvest of ${formatDate(initial.recorded_on)}` : "Add a harvest or sale";

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const qty = String(fd.get("quantity_kg") ?? "").trim();
    const price = String(fd.get("price_pkr_per_kg") ?? "").trim();
    if (!MONEY.test(qty) || Number(qty) <= 0) return setError("Enter the quantity in kg, greater than 0.");
    if (price && !MONEY.test(price)) return setError("Price must be rupees per kg with at most 2 decimals, or empty if not sold.");
    const opt = (k: string) => String(fd.get(k) ?? "").trim() || null;
    setError(null);
    save.mutate(
      { recorded_on: String(fd.get("recorded_on")), quantity_kg: qty, price_pkr_per_kg: price || null, buyer: opt("buyer"), note: opt("note") },
      { onSuccess: () => setOpen(false), onError: (err) => setError(errorMessage(err)) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); setError(null); }}>
      <DialogTrigger asChild>{trigger(initial ? title : undefined, "Add harvest / sale")}</DialogTrigger>
      <DialogContent title={title} description="Quantity in kilograms. Leave the price empty for harvest not sold yet.">
        <form onSubmit={submit} className="grid gap-3" noValidate>
          <FormField label="Date"><Input name="recorded_on" type="date" max={todayIso()} required defaultValue={initial?.recorded_on ?? todayIso()} /></FormField>
          <FormField label="Quantity (kg)"><Input name="quantity_kg" inputMode="decimal" defaultValue={initial?.quantity_kg ?? ""} /></FormField>
          <FormField label="Sale price (PKR per kg)" optional><Input name="price_pkr_per_kg" inputMode="decimal" defaultValue={initial?.price_pkr_per_kg ?? ""} /></FormField>
          <FormField label="Buyer" optional><Input name="buyer" maxLength={120} defaultValue={initial?.buyer ?? ""} /></FormField>
          <FormField label="Note" optional><Input name="note" maxLength={300} defaultValue={initial?.note ?? ""} /></FormField>
          {error && <InlineError message={error} />}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={save.isPending}>{save.isPending ? "Savingâ€¦" : "Save harvest"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
