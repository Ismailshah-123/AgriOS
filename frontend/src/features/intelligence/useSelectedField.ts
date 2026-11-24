import { useEffect } from "react";
import { useSearchParams } from "react-router";
import { useFields } from "@/features/platform/queries";
import type { FieldRecord } from "@/services/api/types";

/** Selected field lives in the URL (?field=) so pages are linkable and the back button works. */
export function useSelectedField(): {
  fieldId: string;
  field: FieldRecord | undefined;
  fields: ReturnType<typeof useFields>;
  setFieldId: (id: string) => void;
} {
  const [params, setParams] = useSearchParams();
  const fields = useFields();
  const items = fields.data?.items ?? [];
  const requested = params.get("field") ?? "";
  const field = items.find((f) => f.id === requested) ?? items[0];
  const setFieldId = (id: string) => setParams({ field: id }, { replace: true });
  useEffect(() => {
    if (field && field.id !== requested) setParams({ field: field.id }, { replace: true });
  }, [field, requested, setParams]);
  return { fieldId: field?.id ?? "", field, fields, setFieldId };
}
