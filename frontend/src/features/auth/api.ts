import { apiRequest } from "@/lib/api";
import type {
  ForgotPasswordFormValues,
  LoginFormValues,
  ResetPasswordFormValues,
  SignupFormValues,
} from "@/features/auth/schemas";

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
};

export type SignupResponse = {
  message: string;
  workspace_id: string;
  onboarding_completed: boolean;
  next_step: string;
};

export type MessageResponse = {
  message: string;
};

export function login(payload: LoginFormValues) {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function signup(payload: SignupFormValues) {
  return apiRequest<SignupResponse>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      email: payload.email,
      password: payload.password,
      company_name: payload.companyName,
      company_website: payload.companyWebsite,
      product_description: payload.productDescription,
      industry: payload.industry,
      target_market: payload.targetMarket,
    }),
  });
}

export function forgotPassword(payload: ForgotPasswordFormValues) {
  return apiRequest<MessageResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resetPassword(token: string, payload: ResetPasswordFormValues) {
  return apiRequest<MessageResponse>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({
      token,
      new_password: payload.password,
    }),
  });
}

export function verifyEmail(token: string) {
  return apiRequest<MessageResponse>(`/auth/verify-email?token=${encodeURIComponent(token)}`);
}
