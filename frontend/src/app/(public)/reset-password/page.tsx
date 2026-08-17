"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { RecoveryCard } from "@/components/auth/recovery-card";
import { resetPassword } from "@/features/auth/api";
import {
  resetPasswordSchema,
  type ResetPasswordFormValues,
} from "@/features/auth/schemas";

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      password: "",
      confirmPassword: "",
    },
  });

  const resetPasswordMutation = useMutation({
    mutationFn: (values: ResetPasswordFormValues) => {
      if (!token) {
        throw new Error("Reset token is missing. Please request a fresh reset link.");
      }

      return resetPassword(token, values);
    },
  });

  const onSubmit = handleSubmit((values) => {
    resetPasswordMutation.mutate(values);
  });

  return (
    <RecoveryCard
      eyebrow="Set New Password"
      title="Choose a new password."
      description="A small, calm reset card keeps the recovery path clear and avoids turning password reset into a maze."
      footer={
        <>
          Need a fresh link?{" "}
          <Link href="/forgot-password" className="font-semibold text-accent">
            Request another reset
          </Link>
        </>
      }
    >
      {!token ? (
        <div className="space-y-5">
          <div className="rounded-[22px] border border-amber-200 bg-amber-50 p-4">
            <p className="text-sm leading-6 text-amber-900">
              This reset link is missing its token. Request a new link and open it from the message the backend sends.
            </p>
          </div>
          <Link
            href="/forgot-password"
            className="primary-button inline-flex h-12 items-center justify-center px-5 font-semibold"
          >
            Request reset link
          </Link>
        </div>
      ) : resetPasswordMutation.isSuccess ? (
        <div className="space-y-5">
          <div className="rounded-[22px] border border-emerald-200 bg-emerald-50 p-4">
            <p className="text-sm leading-6 text-emerald-900">
              {resetPasswordMutation.data.message}
            </p>
          </div>
          <p className="text-sm leading-6 text-muted">
            The backend also revokes active sessions after a successful password reset, so the user gets a clean restart.
          </p>
          <Link
            href="/login"
            className="primary-button inline-flex h-12 items-center justify-center px-5 font-semibold"
          >
            Go to login
          </Link>
        </div>
      ) : (
        <form className="space-y-5" onSubmit={onSubmit}>
          <label className="block space-y-2">
            <span className="text-sm font-semibold text-foreground">New password</span>
            <input
              className="field"
              type="password"
              placeholder="Create a strong password"
              autoComplete="new-password"
              {...register("password")}
            />
            {errors.password ? (
              <p className="text-sm text-danger">{errors.password.message}</p>
            ) : null}
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-semibold text-foreground">Confirm password</span>
            <input
              className="field"
              type="password"
              placeholder="Repeat your new password"
              autoComplete="new-password"
              {...register("confirmPassword")}
            />
            {errors.confirmPassword ? (
              <p className="text-sm text-danger">{errors.confirmPassword.message}</p>
            ) : null}
          </label>

          {resetPasswordMutation.isError ? (
            <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              {resetPasswordMutation.error.message}
            </div>
          ) : null}

          <button
            className="primary-button h-12 w-full font-semibold disabled:cursor-not-allowed disabled:opacity-70"
            type="submit"
            disabled={resetPasswordMutation.isPending}
          >
            {resetPasswordMutation.isPending ? "Resetting password..." : "Reset password"}
          </button>
        </form>
      )}
    </RecoveryCard>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordContent />
    </Suspense>
  );
}
