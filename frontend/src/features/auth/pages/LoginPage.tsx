import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { errorMessage } from "@/utils/format";
import { useAuth } from "../auth-context";
import { AuthLayout } from "./AuthLayout";

const schema = z.object({
  email: z.string().trim().min(1, "Enter your email.").email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
});
type Values = z.infer<typeof schema>;

export function LoginPage() {
  const { login } = useAuth();
  const [serverError, setServerError] = useState<string | null>(null);
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async ({ email, password }) => {
    setServerError(null);
    try {
      // On success PublicOnly redirects to the page originally requested.
      await login(email, password);
    } catch (err) {
      setServerError(errorMessage(err));
    }
  });

  return (
    <AuthLayout title="Sign in" subtitle="Welcome back. Sign in to manage your farms.">
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        {serverError && <InlineError message={serverError} />}
        <FormField label="Email" error={errors.email?.message}>
          <Input type="email" autoComplete="email" {...form.register("email")} />
        </FormField>
        <FormField label="Password" error={errors.password?.message}>
          <Input type="password" autoComplete="current-password" {...form.register("password")} />
        </FormField>
        <Button type="submit" disabled={isSubmitting} className="mt-1">
          {isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="text-sm text-muted">
        New to AgriOS?{" "}
        <Link to="/register" className="font-semibold text-primary-dark hover:underline">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  );
}
