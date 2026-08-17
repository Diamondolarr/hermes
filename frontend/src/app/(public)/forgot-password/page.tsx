"use client";

import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { RecoveryCard } from "@/components/auth/recovery-card";
import { forgotPassword } from "@/features/auth/api";
import {
  forgotPasswordSchema,
  type ForgotPasswordFormValues,
} from "@/features/auth/schemas";

export default function ForgotPasswordPage() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: {
      email: "",
    },
  });

  const forgotPasswordMutation = useMutation({
    mutationFn: forgotPassword,
  });

  const onSubmit = handleSubmit((values) => {
    forgotPasswordMutation.mutate(values);
  });

  return (
    <RecoveryCard
      eyebrow="Quick Recovery"
      title="Send a password reset link."
      description="This screen stays intentionally compact: one field, one decision, and one reassuring next step."
      footer={
        <>
          Back to{' '}
          <Link href="/login" className="font-semibold text-accent">
            log in
          </Link>
        </>
      }
    >
      {forgotPasswordMutation.isSuccess ? (
        <div className="space-y-5">
          <div className="rounded-[22px] border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm leading-6 text-emerald-900">
              {forgotPasswordMutation.data.message}
            </p>
          </div>
          <p className="text-sm leading-6 text-muted">
            For local development, the reset link is printed by the backend email stub. In production this same flow drops into the user&apos;s inbox.
          </p>
          <Link
            href="/login"
            className="primary-button inline-flex h-12 items-center justify-center px-5 font-semibold"
          >
            Return to login
          </Link>
        </div>
      ) : (
        <form className="space-y-5" onSubmit={onSubmit}>
          <label className="block space-y-2">
            <span className="text-sm font-semibold text-foreground">Email</span>
            <input
              className="field"
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              {...register("email")}
            />
            {errors.email ? (
              <p className="text-sm text-danger">{errors.email.message}</p>
            ) : null}
          </label>

          {forgotPasswordMutation.isError ? (
            <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              {forgotPasswordMutation.error.message}
            </div>
          ) : null}

          <button
            className="primary-button h-12 w-full font-semibold disabled:cursor-not-allowed disabled:opacity-70"
            type="submit"
            disabled={forgotPasswordMutation.isPending}
          >
            {forgotPasswordMutation.isPending ? "Sending reset link..." : "Send reset link"}
          </button>
        </form>
      )}
    </RecoveryCard>
  );
}
