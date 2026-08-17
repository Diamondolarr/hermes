"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { StatusBadge } from "@/components/ui/status-badge";
import { useAuth } from "@/lib/auth-context";
import {
  getCompanyProfile,
  getIdealCustomerProfile,
  getOnboardingStatus,
  saveCompanyProfile,
  saveIdealCustomerProfile,
} from "@/features/onboarding/api";
import {
  companyProfileSchema,
  idealCustomerProfileSchema,
  type CompanyProfileFormValues,
  type IdealCustomerProfileFormValues,
} from "@/features/onboarding/schemas";

const steps = [
  {
    id: 1,
    key: "company_profile",
    title: "Company profile",
    subtitle: "Position the workspace",
  },
  {
    id: 2,
    key: "ideal_customer_profile",
    title: "Ideal customer profile",
    subtitle: "Define who we should pursue",
  },
] as const;

const stepTips = {
  1: [
    "This step should feel like a strategic briefing, not a tax form.",
    "We already prefill it from signup when that data exists, so users start with momentum.",
    "Strong company language here improves research, personalization, and campaign framing later.",
  ],
  2: [
    "Comma-separated roles and pain points keep the first version fast without blocking better chips later.",
    "The backend stores these as arrays, so we can upgrade the UI later without changing the data shape.",
    "A clear ICP here sharpens sales insight generation and campaign targeting downstream.",
  ],
} as const;

const companySizeOptions = [
  "1-10 employees",
  "11-50 employees",
  "51-200 employees",
  "201-500 employees",
  "500+ employees",
];

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { session } = useAuth();
  const [activeStep, setActiveStep] = useState<1 | 2>(1);

  const accessToken = session?.accessToken ?? null;

  const companyForm = useForm<CompanyProfileFormValues>({
    resolver: zodResolver(companyProfileSchema),
    defaultValues: {
      companyName: "",
      companyWebsite: "https://",
      productDescription: "",
      industry: "",
      targetMarket: "",
    },
  });

  const idealForm = useForm<IdealCustomerProfileFormValues>({
    resolver: zodResolver(idealCustomerProfileSchema),
    defaultValues: {
      targetIndustry: "",
      targetCompanySize: "11-50 employees",
      targetRolesInput: "",
      targetRegion: "",
      painPointsInput: "",
    },
  });

  const statusQuery = useQuery({
    queryKey: ["onboarding", "status"],
    queryFn: () => getOnboardingStatus(accessToken as string),
    enabled: Boolean(accessToken),
  });

  const companyQuery = useQuery({
    queryKey: ["onboarding", "company-profile"],
    queryFn: () => getCompanyProfile(accessToken as string),
    enabled: Boolean(accessToken),
  });

  const idealQuery = useQuery({
    queryKey: ["onboarding", "ideal-customer-profile"],
    queryFn: () => getIdealCustomerProfile(accessToken as string),
    enabled: Boolean(accessToken),
  });

  useEffect(() => {
    if (!companyQuery.data) {
      return;
    }

    companyForm.reset({
      companyName: companyQuery.data.company_name,
      companyWebsite: companyQuery.data.company_website,
      productDescription: companyQuery.data.product_description,
      industry: companyQuery.data.industry,
      targetMarket: companyQuery.data.target_market,
    });
  }, [companyForm, companyQuery.data]);

  useEffect(() => {
    if (!idealQuery.data) {
      return;
    }

    idealForm.reset({
      targetIndustry: idealQuery.data.target_industry,
      targetCompanySize: idealQuery.data.target_company_size,
      targetRolesInput: idealQuery.data.target_roles.join(", "),
      targetRegion: idealQuery.data.target_region,
      painPointsInput: idealQuery.data.pain_points.join(", "),
    });
  }, [idealForm, idealQuery.data]);

  useEffect(() => {
    if (!statusQuery.data) {
      return;
    }

    if (statusQuery.data.onboarding_completed || statusQuery.data.next_step === "completed") {
      router.replace("/dashboard");
      return;
    }

    setActiveStep(statusQuery.data.next_step === "ideal_customer_profile" ? 2 : 1);
  }, [router, statusQuery.data]);

  const companyMutation = useMutation({
    mutationFn: (values: CompanyProfileFormValues) =>
      saveCompanyProfile(accessToken as string, values),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["onboarding", "status"] }),
        queryClient.invalidateQueries({ queryKey: ["onboarding", "company-profile"] }),
      ]);
      setActiveStep(2);
    },
  });

  const idealMutation = useMutation({
    mutationFn: (values: IdealCustomerProfileFormValues) =>
      saveIdealCustomerProfile(accessToken as string, values),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["onboarding", "status"] }),
        queryClient.invalidateQueries({ queryKey: ["onboarding", "ideal-customer-profile"] }),
      ]);
      router.push("/dashboard");
    },
  });

  const isLoading = statusQuery.isLoading || companyQuery.isLoading || idealQuery.isLoading;
  const queryError = statusQuery.error || companyQuery.error || idealQuery.error;

  const currentTips = useMemo(() => stepTips[activeStep], [activeStep]);

  if (isLoading) {
    return (
      <div className="min-h-screen p-4">
        <div className="panel-strong flex min-h-[calc(100vh-2rem)] items-center justify-center p-8 text-center">
          <div>
            <p className="eyebrow">Onboarding</p>
            <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">
              Preparing your workspace wizard.
            </h1>
            <p className="mt-4 max-w-lg text-lg text-muted">
              We are loading the saved company context so the onboarding flow starts prefilled instead of blank.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (queryError) {
    return (
      <div className="min-h-screen p-4">
        <div className="panel-strong flex min-h-[calc(100vh-2rem)] items-center justify-center p-8 text-center">
          <div>
            <p className="eyebrow">Onboarding</p>
            <h1 className="heading-display mt-4 text-4xl font-semibold text-foreground">
              We hit a setup snag.
            </h1>
            <p className="mt-4 max-w-xl text-lg text-muted">
              {queryError.message}
            </p>
            <button
              className="primary-button mt-6 inline-flex h-11 items-center px-5 font-semibold"
              type="button"
              onClick={() => router.refresh()}
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const submitCompanyStep = companyForm.handleSubmit((values) => {
    companyMutation.mutate(values);
  });

  const submitIdealStep = idealForm.handleSubmit((values) => {
    idealMutation.mutate(values);
  });

  return (
    <div className="min-h-screen p-3 sm:p-4 lg:p-5">
      <div className="grid min-h-[calc(100vh-2rem)] gap-4 xl:grid-cols-[0.24fr_0.52fr_0.24fr]">
        <aside className="panel p-5 sm:p-6">
          <div className="rounded-[26px] bg-[linear-gradient(160deg,rgba(15,118,110,0.12),rgba(15,118,110,0.02))] p-5">
            <p className="eyebrow">Workspace Setup</p>
            <h1 className="heading-display mt-4 text-3xl font-semibold text-foreground">
              Onboarding wizard
            </h1>
            <p className="mt-3 text-sm leading-6 text-muted">
              A full-page onboarding flow gives the workspace its strategic context before the broader command center opens up.
            </p>
          </div>

          <div className="mt-6 space-y-4">
            {steps.map((step) => {
              const isActive = step.id === activeStep;
              const isComplete = step.id < activeStep;

              return (
                <div
                  key={step.id}
                  className={`rounded-[24px] border p-4 transition ${
                    isActive
                      ? "border-transparent bg-surface-ink text-white shadow-[0_20px_44px_-28px_rgba(17,32,30,0.8)]"
                      : isComplete
                        ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                        : "border-border/70 bg-white/70 text-foreground"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className={`flex h-10 w-10 items-center justify-center rounded-full font-mono text-sm font-semibold ${
                      isActive
                        ? "bg-white/12 text-white"
                        : isComplete
                          ? "bg-emerald-200 text-emerald-900"
                          : "bg-accent-soft text-accent"
                    }`}>
                      0{step.id}
                    </div>
                    <StatusBadge tone={isComplete ? "accent" : isActive ? "ink" : "neutral"}>
                      {isComplete ? "Complete" : isActive ? "Current" : "Next"}
                    </StatusBadge>
                  </div>
                  <p className={`mt-4 text-base font-semibold ${isActive ? "text-white" : "text-foreground"}`}>
                    {step.title}
                  </p>
                  <p className={`mt-2 text-sm leading-6 ${isActive ? "text-white/72" : "text-muted"}`}>
                    {step.subtitle}
                  </p>
                </div>
              );
            })}
          </div>
        </aside>

        <main className="panel-strong p-6 sm:p-8">
          <div className="flex flex-col gap-4 border-b border-border/70 pb-6 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="eyebrow">Step 0{activeStep}</p>
              <h2 className="heading-display mt-3 text-4xl font-semibold text-foreground">
                {activeStep === 1 ? "Position the company profile." : "Shape the ideal customer profile."}
              </h2>
              <p className="mt-3 max-w-2xl text-lg leading-7 text-muted">
                {activeStep === 1
                  ? "This is the operating context the AI will use for research, outreach, and campaign framing."
                  : "Now we narrow the focus so the SDR knows which buyers, regions, and pressure points matter most."}
              </p>
            </div>
            <StatusBadge tone="accent">
              {statusQuery.data?.workspace_id ? "Workspace ready" : "Preparing"}
            </StatusBadge>
          </div>

          {activeStep === 1 ? (
            <form className="mt-8 grid gap-5" onSubmit={submitCompanyStep}>
              <label className="block space-y-2">
                <span className="text-sm font-semibold text-foreground">Company name</span>
                <input className="field" type="text" placeholder="Northline AI" {...companyForm.register("companyName")} />
                {companyForm.formState.errors.companyName ? (
                  <p className="text-sm text-danger">{companyForm.formState.errors.companyName.message}</p>
                ) : null}
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-semibold text-foreground">Company website</span>
                <input className="field" type="url" placeholder="https://northline.ai" {...companyForm.register("companyWebsite")} />
                {companyForm.formState.errors.companyWebsite ? (
                  <p className="text-sm text-danger">{companyForm.formState.errors.companyWebsite.message}</p>
                ) : null}
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-semibold text-foreground">Product description</span>
                <textarea
                  className="field min-h-40 resize-none"
                  placeholder="Describe what your company sells, the buyer it serves, and the outcome it helps create."
                  {...companyForm.register("productDescription")}
                />
                {companyForm.formState.errors.productDescription ? (
                  <p className="text-sm text-danger">{companyForm.formState.errors.productDescription.message}</p>
                ) : null}
              </label>

              <div className="grid gap-5 md:grid-cols-2">
                <label className="block space-y-2">
                  <span className="text-sm font-semibold text-foreground">Industry</span>
                  <input className="field" type="text" placeholder="B2B SaaS" {...companyForm.register("industry")} />
                  {companyForm.formState.errors.industry ? (
                    <p className="text-sm text-danger">{companyForm.formState.errors.industry.message}</p>
                  ) : null}
                </label>

                <label className="block space-y-2">
                  <span className="text-sm font-semibold text-foreground">Target market</span>
                  <input className="field" type="text" placeholder="Mid-market revenue teams" {...companyForm.register("targetMarket")} />
                  {companyForm.formState.errors.targetMarket ? (
                    <p className="text-sm text-danger">{companyForm.formState.errors.targetMarket.message}</p>
                  ) : null}
                </label>
              </div>

              {companyMutation.isError ? (
                <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                  {companyMutation.error.message}
                </div>
              ) : null}

              <div className="flex flex-wrap justify-end gap-3 border-t border-border/70 pt-6">
                <button
                  className="primary-button inline-flex h-12 items-center px-6 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                  type="submit"
                  disabled={companyMutation.isPending}
                >
                  {companyMutation.isPending ? "Saving..." : "Continue"}
                </button>
              </div>
            </form>
          ) : (
            <form className="mt-8 grid gap-5" onSubmit={submitIdealStep}>
              <div className="grid gap-5 md:grid-cols-2">
                <label className="block space-y-2">
                  <span className="text-sm font-semibold text-foreground">Target industry</span>
                  <input className="field" type="text" placeholder="B2B SaaS" {...idealForm.register("targetIndustry")} />
                  {idealForm.formState.errors.targetIndustry ? (
                    <p className="text-sm text-danger">{idealForm.formState.errors.targetIndustry.message}</p>
                  ) : null}
                </label>

                <label className="block space-y-2">
                  <span className="text-sm font-semibold text-foreground">Target company size</span>
                  <select className="field" {...idealForm.register("targetCompanySize")}>
                    {companySizeOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                  {idealForm.formState.errors.targetCompanySize ? (
                    <p className="text-sm text-danger">{idealForm.formState.errors.targetCompanySize.message}</p>
                  ) : null}
                </label>
              </div>

              <label className="block space-y-2">
                <span className="text-sm font-semibold text-foreground">Target roles</span>
                <textarea
                  className="field min-h-28 resize-none"
                  placeholder="Revenue Operations, VP Sales, Head of Growth"
                  {...idealForm.register("targetRolesInput")}
                />
                <p className="text-sm text-muted">Separate roles with commas.</p>
                {idealForm.formState.errors.targetRolesInput ? (
                  <p className="text-sm text-danger">{idealForm.formState.errors.targetRolesInput.message}</p>
                ) : null}
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-semibold text-foreground">Target region</span>
                <input className="field" type="text" placeholder="North America" {...idealForm.register("targetRegion")} />
                {idealForm.formState.errors.targetRegion ? (
                  <p className="text-sm text-danger">{idealForm.formState.errors.targetRegion.message}</p>
                ) : null}
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-semibold text-foreground">Pain points</span>
                <textarea
                  className="field min-h-32 resize-none"
                  placeholder="Low reply rate, slow outbound ramp, poor lead quality"
                  {...idealForm.register("painPointsInput")}
                />
                <p className="text-sm text-muted">Separate pain points with commas.</p>
                {idealForm.formState.errors.painPointsInput ? (
                  <p className="text-sm text-danger">{idealForm.formState.errors.painPointsInput.message}</p>
                ) : null}
              </label>

              {idealMutation.isError ? (
                <div className="rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                  {idealMutation.error.message}
                </div>
              ) : null}

              <div className="flex flex-wrap justify-between gap-3 border-t border-border/70 pt-6">
                <button
                  className="secondary-button inline-flex h-12 items-center px-6 font-semibold"
                  type="button"
                  onClick={() => setActiveStep(1)}
                >
                  Back
                </button>
                <button
                  className="primary-button inline-flex h-12 items-center px-6 font-semibold disabled:cursor-not-allowed disabled:opacity-70"
                  type="submit"
                  disabled={idealMutation.isPending}
                >
                  {idealMutation.isPending ? "Finishing..." : "Finish setup"}
                </button>
              </div>
            </form>
          )}
        </main>

        <aside className="panel hidden xl:block xl:p-6">
          <p className="eyebrow">Contextual Tips</p>
          <h2 className="heading-display mt-4 text-3xl font-semibold text-foreground">
            Why this step matters
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            The right rail is meant to coach the user without crowding the main form. It gives strategic context while the form stays focused.
          </p>

          <div className="mt-8 space-y-4">
            {currentTips.map((tip, index) => (
              <div key={tip} className="rounded-[24px] border border-border/70 bg-white/75 p-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft font-mono text-sm font-semibold text-accent">
                  0{index + 1}
                </div>
                <p className="mt-4 text-sm leading-6 text-muted">{tip}</p>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
