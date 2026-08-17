import { ApiError, apiRequest } from "@/lib/api";
import type {
  CompanyProfileFormValues,
  IdealCustomerProfileFormValues,
} from "@/features/onboarding/schemas";

export type OnboardingStatusResponse = {
  workspace_id: string;
  onboarding_completed: boolean;
  next_step: "company_profile" | "ideal_customer_profile" | "completed";
};

export type CompanyProfileResponse = {
  company_name: string;
  company_website: string;
  product_description: string;
  industry: string;
  target_market: string;
};

export type IdealCustomerProfileResponse = {
  target_industry: string;
  target_company_size: string;
  target_roles: string[];
  target_region: string;
  pain_points: string[];
};

type MessageResponse = {
  message: string;
};

function parseCsvList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function getOnboardingStatus(accessToken: string) {
  return apiRequest<OnboardingStatusResponse>("/onboarding/status", {
    method: "GET",
    accessToken,
  });
}

export async function getCompanyProfile(accessToken: string) {
  try {
    return await apiRequest<CompanyProfileResponse>("/onboarding/company-profile", {
      method: "GET",
      accessToken,
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function getIdealCustomerProfile(accessToken: string) {
  try {
    return await apiRequest<IdealCustomerProfileResponse>(
      "/onboarding/ideal-customer-profile",
      {
        method: "GET",
        accessToken,
      },
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function saveCompanyProfile(
  accessToken: string,
  payload: CompanyProfileFormValues,
) {
  return apiRequest<MessageResponse>("/onboarding/company-profile", {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      company_name: payload.companyName,
      company_website: payload.companyWebsite,
      product_description: payload.productDescription,
      industry: payload.industry,
      target_market: payload.targetMarket,
    }),
  });
}

export function saveIdealCustomerProfile(
  accessToken: string,
  payload: IdealCustomerProfileFormValues,
) {
  return apiRequest<MessageResponse>("/onboarding/ideal-customer-profile", {
    method: "POST",
    accessToken,
    body: JSON.stringify({
      target_industry: payload.targetIndustry,
      target_company_size: payload.targetCompanySize,
      target_roles: parseCsvList(payload.targetRolesInput),
      target_region: payload.targetRegion,
      pain_points: parseCsvList(payload.painPointsInput),
    }),
  });
}
