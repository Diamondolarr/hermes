"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { login } from "@/features/auth/api";
import { LoginFormValues, loginSchema } from "@/features/auth/schemas";
import { useAuth } from "@/lib/auth-context";

const trustSignals = [
  {
    title: "One place for the full motion",
    body: "Leads, campaigns, replies, approvals, and analytics all live in the same operating rhythm.",
  },
  {
    title: "Calm by design",
    body: "The interface stays readable even when the system gets busy, so users can make decisions quickly.",
  },
  {
    title: "Built for handoff",
    body: "Humans can step in at the right moments without losing the AI context that got us there.",
  },
];

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setSession } = useAuth();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (result, variables) => {
      setSession({
        accessToken: result.access_token,
        tokenType: result.token_type,
        expiresAt: result.expires_at,
        email: variables.email,
      });

      const requestedNext = searchParams.get("next");
      const next =
        requestedNext && requestedNext.startsWith("/")
          ? requestedNext
          : "/dashboard";
      router.push(next);
    },
  });

  const onSubmit = handleSubmit((values) => {
    loginMutation.mutate(values);
  });

  return (
    <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-7xl items-center justify-center">
      <div className="grid w-full overflow-hidden rounded-[32px] border border-border/70 bg-white/40 shadow-[0_40px_120px_-48px_rgba(17,32,30,0.45)] backdrop-blur xl:grid-cols-[1.05fr_0.95fr]">
        <section className="relative overflow-hidden bg-[linear-gradient(160deg,#122826_0%,#184440_45%,#26655a_100%)] p-8 text-white sm:p-10 lg:p-14">
          <div className="absolute -left-16 top-10 h-48 w-48 rounded-full bg-white/10 blur-3xl" />
          <div className="absolute bottom-0 right-0 h-64 w-64 rounded-full bg-[rgba(199,113,76,0.24)] blur-3xl" />

          <div className="relative flex h-full flex-col justify-between gap-8">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.24em] text-white/70">AI SDR</p>
              <h1 className="heading-display mt-6 max-w-xl text-5xl font-semibold leading-[1.02] sm:text-6xl">
                Calm sign-in for a busy outbound machine.
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-7 text-white/76">
                This left side is the brand and story surface: aspirational enough to feel premium, grounded enough to still feel operational.
              </p>
            </div>

            <div className="grid gap-4">
              {trustSignals.map((signal, index) => (
                <div key={signal.title} className="rounded-[24px] border border-white/12 bg-white/8 p-5 backdrop-blur">
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white/12 font-mono text-xs font-semibold text-white/85">
                      0{index + 1}
                    </div>
                    <p className="text-sm font-semibold text-white">{signal.title}</p>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-white/72">{signal.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="flex items-center justify-center bg-[linear-gradient(180deg,rgba(255,252,246,0.92),rgba(248,241,231,0.98))] p-6 sm:p-8 lg:p-12">
          <div className="w-full max-w-md rounded-[30px] border border-border/80 bg-white/78 p-6 shadow-[0_32px_80px_-42px_rgba(17,32,30,0.34)] backdrop-blur sm:p-8">
            <p className="eyebrow">Welcome Back</p>
            <h2 className="heading-display mt-3 text-4xl font-semibold text-foreground">Log in</h2>
            <p className="mt-3 text-base leading-7 text-muted">
              Pick up where you left off: inbox triage, campaign approvals, and the full dashboard are waiting behind one clean sign-in.
            </p>

            <form className="mt-8 space-y-5" onSubmit={onSubmit}>
              <label className="block space-y-2">
                <span className="text-sm font-semibold text-foreground">Email</span>
                <input
                  className="field"
                  type="email"
                  placeholder="you@company.com"
                  autoComplete="email"
                  {...register("email")}
                />
                {errors.email ? <p className="text-sm text-danger">{errors.email.message}</p> : null}
              </label>

              <label className="block space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-foreground">Password</span>
                  <Link href="/forgot-password" className="text-sm font-semibold text-accent">
                    Forgot password?
                  </Link>
                </div>
                <input
                  className="field"
                  type="password"
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  {...register("password")}
                />
                {errors.password ? <p className="text-sm text-danger">{errors.password.message}</p> : null}
              </label>

              {loginMutation.isError ? (
                <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                  {loginMutation.error.message}
                </div>
              ) : null}

              <button
                className="primary-button h-12 w-full font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                type="submit"
                disabled={loginMutation.isPending}
              >
                {loginMutation.isPending ? "Logging you in..." : "Log in"}
              </button>
            </form>

            <p className="mt-6 text-sm text-muted">
              Don&apos;t have an account?{' '}
              <Link href="/signup" className="font-semibold text-accent">
                Sign up
              </Link>
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}
