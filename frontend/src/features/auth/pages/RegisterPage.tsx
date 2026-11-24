import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/services/api/client";
import { errorMessage } from "@/utils/format";
import { useAuth } from "../auth-context";
import { AuthLayout } from "./AuthLayout";

// Mirrors backend RegisterRequest (app/identity/schemas.py).
const schema = z.object({
  full_name: z.string().trim().min(1, "Enter your name.").max(120, "Use 120 characters or fewer."),
  email: z.string().trim().min(1, "Enter your email.").email("Enter a valid email address."),
  password: z
    .string()
    .min(10, "Use at least 10 characters.")
    .max(128, "Use 128 characters or fewer."),
});
type Values = z.infer<typeof schema>;

export function RegisterPage() {
  const { register: signUp } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", password: "" },
  });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (v) => {
    setServerError(null);
    try {
      // On success PublicOnly redirects to the Overview.
      await signUp(v.full_name, v.email, v.password);
    } catch (err) {
      if (err instanceof ApiError && err.field && err.field in v) {
        form.setError(err.field as keyof Values, { message: err.message });
      } else {
        setServerError(errorMessage(err));
      }
    }
  });

  return (
    <AuthLayout title="Create your account" subtitle="Start with your farm records. It takes a minute.">
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {serverError && <InlineError message={serverError} />}
        <FormField label="Full name" error={errors.full_name?.message}>
          <Input autoComplete="name" {...form.register("full_name")} />
        </FormField>
        <FormField label="Email" error={errors.email?.message}>
          <Input type="email" autoComplete="email" {...form.register("email")} />
        </FormField>
        <FormField
          label="Password"
          error={errors.password?.message}
          hint={errors.password ? undefined : "At least 10 characters. A short phrase works well."}
        >
          <Input type="password" autoComplete="new-password" {...form.register("password")} />
        </FormField>
        <Button type="submit" disabled={isSubmitting} className="mt-1">
          {isSubmitting ? "Creating account…" : "Create account"}
        </Button>
      </form>
      <p className="text-sm text-muted">
        Already have an account?{" "}
        <Link to="/login" className="font-semibold text-primary-dark hover:underline">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  );
}
