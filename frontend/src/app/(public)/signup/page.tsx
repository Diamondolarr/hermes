"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { signup } from "@/features/auth/api";
import { SignupFormValues, signupSchema } from "@/features/auth/schemas";

const sections = [
  {
    title: "Account",
    description: "The essentials for secure access and workspace ownership.",
  },
  {
    title: "Company profile prefill",
    description: "These fields seed onboarding so the user doesn&apos;t repeat themselves after signup.",
  },
];

export default function SignupPage() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      companyName: "",
      companyWebsite: "https://",
      productDescription: "",
      industry: "",
      targetMarket: "",
    },
  });

  const signupMutation = useMutation({
    mutationFn: signup,
    onSuccess: (_, variables) => {
      router.push(`/verify-email?status=pending&email=${encodeURIComponent(variables.email)}`);
    },
  });

  const onSubmit = handleSubmit((values) => {
    signupMutation.mutate(values);
  });

  return (
    <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-5xl items-center justify-center">
      <div className="panel-strong soft-ring w-full overflow-hidden p-6 sm:p-8 lg:p-10">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="eyebrow">Step 1 Of 1</p>
            <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground sm:text-5xl">
              Create the workspace and prefill the story your SDR will tell.
            </h1>
            <p className="mt-4 max-w-2xl text-lg leading-7 text-muted">
              This signup is intentionally multi-section instead of cramped. It keeps the user oriented while still collecting the company context your backend needs on day one.
            </p>
          </div>

          <div className="rounded-[26px] border border-border/70 bg-white/72 p-4 lg:max-w-sm">
            <div className="flex gap-2">
              <div className="h-2 flex-1 rounded-full bg-accent" />
              <div className="h-2 flex-1 rounded-full bg-accent/25" />
            </div>
            <p className="mt-4 text-sm leading-6 text-muted">
              Friendly progress framing, not a dense form wall. We’re showing the user what this setup unlocks instead of dumping fields with no context.
            </p>
          </div>
        </div>

        <div className="mt-8 grid gap-8 lg:grid-cols-[0.34fr_0.66fr]">
          <aside className="space-y-4">
            {sections.map((section, index) => (
              <div key={section.title} className="rounded-[24px] border border-border/70 bg-white/70 p-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft font-mono text-sm font-semibold text-accent">
                  0{index + 1}
                </div>
                <h2 className="mt-4 text-base font-semibold text-foreground">{section.title}</h2>
                <p className="mt-2 text-sm leading-6 text-muted">{section.description}</p>
              </div>
            ))}
          </aside>

          <form className="rounded-[30px] border border-border/80 bg-white/76 p-6 sm:p-8" onSubmit={onSubmit}>
            <div className="grid gap-6">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-muted">Account</p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="block space-y-2 sm:col-span-2">
                    <span className="text-sm font-semibold text-foreground">Name</span>
                    <input className="field" type="text" placeholder="Jane Doe" {...register("name")} />
                    {errors.name ? <p className="text-sm text-danger">{errors.name.message}</p> : null}
                  </label>

                  <label className="block space-y-2">
                    <span className="text-sm font-semibold text-foreground">Email</span>
                    <input className="field" type="email" placeholder="jane@company.com" autoComplete="email" {...register("email")} />
                    {errors.email ? <p className="text-sm text-danger">{errors.email.message}</p> : null}
                  </label>

                  <label className="block space-y-2">
                    <span className="text-sm font-semibold text-foreground">Password</span>
                    <input className="field" type="password" placeholder="Create a strong password" autoComplete="new-password" {...register("password")} />
                    {errors.password ? <p className="text-sm text-danger">{errors.password.message}</p> : null}
                  </label>
                </div>
              </div>

              <div className="border-t border-border/70 pt-6">
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-muted">Company Profile Prefill</p>
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="block space-y-2">
                    <span className="text-sm font-semibold text-foreground">Company name</span>
                    <input className="field" type="text" placeholder="Northline AI" {...register("companyName")} />
                    {errors.companyName ? <p className="text-sm text-danger">{errors.companyName.message}</p> : null}
                  </label>

                  <label className="block space-y-2">
                    <span className="text-sm font-semibold text-foreground">Company website</span>
                    <input className="field" type="url" placeholder="https://northline.ai" {...register("companyWebsite")} />
                    {errors.companyWebsite ? <p className="text-sm text-danger">{errors.companyWebsite.message}</p> : null}
                  </label>

                  <label className="block space-y-2 sm:col-span-2">
                    <span className="text-sm font-semibold text-foreground">Product description</span>
                    <textarea className="field min-h-32 resize-none" placeholder="Describe what your company sells and who it helps." {...register("productDescription")} />
                    {errors.productDescription ? <p className="text-sm text-danger">{errors.productDescription.message}</p> : null}
                  </label>

                  <label className="block space-y-2">
                    <span className="text-sm font-semibold text-foreground">Industry</span>
                    <input className="field" type="text" placeholder="B2B SaaS" {...register("industry")} />
                    {errors.industry ? <p className="text-sm text-danger">{errors.industry.message}</p> : null}
                  </label>

                  <label className="block space-y-2">
                    <span className="text-sm font-semibold text-foreground">Target market</span>
                    <input className="field" type="text" placeholder="Mid-market revenue teams" {...register("targetMarket")} />
                    {errors.targetMarket ? <p className="text-sm text-danger">{errors.targetMarket.message}</p> : null}
                  </label>
                </div>
              </div>

              {signupMutation.isError ? (
                <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                  {signupMutation.error.message}
                </div>
              ) : null}

              <div className="flex flex-col gap-4 border-t border-border/70 pt-6 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-muted">
                  Already have an account?{' '}
                  <Link href="/login" className="font-semibold text-accent">
                    Log in
                  </Link>
                </p>

                <button
                  className="primary-button h-12 px-6 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                  type="submit"
                  disabled={signupMutation.isPending}
                >
                  {signupMutation.isPending ? "Creating account..." : "Create account"}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
