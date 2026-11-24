import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select } from "@/components/ui/input";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/services/api/client";
import { authApi } from "@/services/api/platform";
import type { Locale } from "@/services/api/types";
import { errorMessage } from "@/utils/format";

const profileSchema = z.object({
  full_name: z.string().trim().min(1, "Enter your name.").max(120, "Use 120 characters or fewer."),
  locale: z.enum(["en", "ur"]),
});

const passwordSchema = z.object({
  current_password: z.string().min(1, "Enter your current password."),
  new_password: z.string().min(10, "Use at least 10 characters.").max(128, "Use 128 characters or fewer."),
});

function Saved({ show }: { show: boolean }) {
  return (
    <p role="status" className="text-sm font-medium text-primary-dark">
      {show ? "Saved." : ""}
    </p>
  );
}

function ProfileCard() {
  const { user, setUser } = useAuth();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: user?.full_name ?? "", locale: user?.locale ?? "en" },
  });
  const onSubmit = form.handleSubmit(async (v) => {
    setSaved(false);
    setError(null);
    try {
      setUser(await authApi.updateProfile({ full_name: v.full_name, locale: v.locale as Locale }));
      setSaved(true);
    } catch (err) {
      setError(errorMessage(err));
    }
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>{user?.email}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="flex max-w-md flex-col gap-4">
          {error && <InlineError message={error} />}
          <FormField label="Full name" error={form.formState.errors.full_name?.message}>
            <Input autoComplete="name" {...form.register("full_name")} />
          </FormField>
          <FormField label="Language" hint="Urdu (right-to-left) currently covers navigation and menus; other text stays in English until reviewed translations are added.">
            <Select {...form.register("locale")}>
              <option value="en">English</option>
              <option value="ur">اردو (Urdu)</option>
            </Select>
          </FormField>
          <div className="flex items-center gap-4">
            <Button type="submit" disabled={form.formState.isSubmitting}>
              Save profile
            </Button>
            <Saved show={saved} />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function PasswordCard() {
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: "", new_password: "" },
  });
  const onSubmit = form.handleSubmit(async (v) => {
    setSaved(false);
    setError(null);
    try {
      await authApi.changePassword(v);
      form.reset();
      setSaved(true);
    } catch (err) {
      if (err instanceof ApiError && err.field === "current_password") {
        form.setError("current_password", { message: err.message });
      } else {
        setError(errorMessage(err));
      }
    }
  });
  const { errors } = form.formState;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>Changing your password signs out your other devices.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} noValidate className="flex max-w-md flex-col gap-4">
          {error && <InlineError message={error} />}
          <FormField label="Current password" error={errors.current_password?.message}>
            <Input type="password" autoComplete="current-password" {...form.register("current_password")} />
          </FormField>
          <FormField label="New password" error={errors.new_password?.message}>
            <Input type="password" autoComplete="new-password" {...form.register("new_password")} />
          </FormField>
          <div className="flex items-center gap-4">
            <Button type="submit" disabled={form.formState.isSubmitting}>
              Change password
            </Button>
            <Saved show={saved} />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Your profile and sign-in details." />
      <div className="flex flex-col gap-6">
        <ProfileCard />
        <PasswordCard />
      </div>
    </>
  );
}
