export type Theme = "dark" | "light";

export const initialTheme = (stored: string | null | undefined): Theme =>
  stored === "dark" || stored === "light" ? stored : "light";
