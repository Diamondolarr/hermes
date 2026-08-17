import { z } from "zod";

export const companyProfileSchema = z.object({
  companyName: z.string().min(1, "Company name is required."),
  companyWebsite: z
    .string()
    .url("Enter a valid website URL, including https://."),
  productDescription: z
    .string()
    .min(1, "Product description is required.")
    .max(1000, "Keep the description under 1000 characters."),
  industry: z.string().min(1, "Industry is required."),
  targetMarket: z.string().min(1, "Target market is required."),
});

export const idealCustomerProfileSchema = z.object({
  targetIndustry: z.string().min(1, "Target industry is required."),
  targetCompanySize: z.string().min(1, "Target company size is required."),
  targetRolesInput: z
    .string()
    .min(1, "Add at least one target role.")
    .refine(
      (value) => value.split(",").map((item) => item.trim()).filter(Boolean).length > 0,
      "Add at least one target role.",
    ),
  targetRegion: z.string().min(1, "Target region is required."),
  painPointsInput: z
    .string()
    .min(1, "Add at least one pain point.")
    .refine(
      (value) => value.split(",").map((item) => item.trim()).filter(Boolean).length > 0,
      "Add at least one pain point.",
    ),
});

export type CompanyProfileFormValues = z.infer<typeof companyProfileSchema>;
export type IdealCustomerProfileFormValues = z.infer<
  typeof idealCustomerProfileSchema
>;
