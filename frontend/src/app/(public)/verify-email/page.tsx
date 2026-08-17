"use client";

import Link from "next/link";
import { Suspense, useEffect, useRef } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { verifyEmail } from "@/features/auth/api";

const stateStyles = {
  pending: "border-amber-200 bg-amber-50 text-amber-900",
  loading: "border-teal-200 bg-teal-50 text-teal-900",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  error: "border-rose-200 bg-rose-50 text-rose-900",
} as const;

const stateLabels = {
  pending: "Verification pending",
  loading: "Verifying",
  success: "Verified successfully",
  error: "Invalid or expired link",
} as const;

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const pendingEmail = searchParams.get("email");
  const pendingStatus = searchParams.get("status");
  const hasTriggered = useRef(false);

  const verificationMutation = useMutation({
    mutationFn: verifyEmail,
  });

  useEffect(() => {
    if (!token || hasTriggered.current) {
      return;
    }

    hasTriggered.current = true;
    verificationMutation.mutate(token);
  }, [token, verificationMutation]);

  const cardState = !token
    ? pendingStatus === "pending"
      ? "pending"
      : "error"
    : verificationMutation.isPending
      ? "loading"
      : verificationMutation.isSuccess
        ? "success"
        : verificationMutation.isError
          ? "error"
          : "loading";

  const title =
    cardState === "pending"
      ? "Check your inbox to finish verification."
      : cardState === "loading"
        ? "Verifying your email now."
        : cardState === "success"
          ? "Your email is verified."
          : "This verification link is not valid anymore.";

  const description =
    cardState === "pending"
      ? `We sent a verification link${pendingEmail ? ` for ${pendingEmail}` : ""}. Open it from the email stub output or inbox to continue.`
      : cardState === "loading"
        ? "We’re validating the token with the backend and preparing the account for sign-in."
        : cardState === "success"
          ? verificationMutation.data?.message ?? "Email verified successfully."
          : verificationMutation.error?.message ?? "The link is missing, expired, or no longer valid.";

  return (
    <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-4xl items-center justify-center px-4 py-6">
      <div className="panel-strong soft-ring w-full max-w-2xl overflow-hidden p-6 sm:p-8">
        <div className="rounded-[26px] bg-[linear-gradient(135deg,rgba(15,118,110,0.12),rgba(199,113,76,0.08))] p-5">
          <p className="eyebrow">Verification</p>
          <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">{title}</h1>
          <p className="mt-3 text-base leading-7 text-muted">{description}</p>
        </div>

        <div className={`mt-6 rounded-[24px] border p-5 ${stateStyles[cardState]}`}>
          <span className="inline-flex rounded-full bg-white/65 px-3 py-1 text-xs font-semibold">
            {stateLabels[cardState]}
          </span>
          <p className="mt-4 text-sm leading-6">
            {cardState === "success"
              ? "You can log in and continue into the rest of the workspace flow."
              : cardState === "loading"
                ? "This page is now the user-facing handoff for verification, while the FastAPI endpoint stays behind the scenes."
                : cardState === "pending"
                  ? "I kept this lightweight pending state so signup has a friendly destination before the user clicks the link."
                  : "If the link has expired, the next clean step is to request a fresh verification flow later or create a new account for now."}
          </p>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/login" className="primary-button inline-flex h-11 items-center px-5 font-semibold">
            Go to login
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmailContent />
    </Suspense>
  );
}
