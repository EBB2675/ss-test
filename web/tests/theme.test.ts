import { describe, expect, it } from "vitest";
import { initialTheme } from "../src/utils/theme";

describe("initialTheme", () => {
  it("keeps a stored theme", () => {
    expect(initialTheme("dark")).toBe("dark");
    expect(initialTheme("light")).toBe("light");
  });

  it("falls back to light when nothing valid is stored", () => {
    for (const stored of [null, undefined, "", "blue"]) {
      expect(initialTheme(stored)).toBe("light");
    }
  });
});
