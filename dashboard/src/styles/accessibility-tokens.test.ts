// @ts-expect-error -- Vitest provides Node built-ins; the browser bundle intentionally omits Node types.
import { readFileSync } from "node:fs";
// @ts-expect-error -- Vitest provides Node built-ins; the browser bundle intentionally omits Node types.
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

declare const process: { cwd(): string };

const tokensCss = readFileSync(resolve(process.cwd(), "src/styles/tokens.css"), "utf8");

function declarationBlock(theme: "light" | "dark") {
  const pattern =
    theme === "light" ? /:root\s*\{([\s\S]*?)\}/ : /\[data-theme="dark"\]\s*\{([\s\S]*?)\}/;
  const match = tokensCss.match(pattern);
  if (!match) throw new Error(`Missing ${theme} token block`);
  return match[1];
}

function token(theme: "light" | "dark", name: string) {
  const match = declarationBlock(theme).match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"));
  if (!match) throw new Error(`Missing hexadecimal --${name} token for ${theme}`);
  return match[1];
}

function contrast(foreground: string, background: string) {
  const luminance = (hex: string) => {
    const channels = [1, 3, 5].map(
      (index) => Number.parseInt(hex.slice(index, index + 2), 16) / 255,
    );
    const linear = channels.map((value) =>
      value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4,
    );
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  };
  const lighter = Math.max(luminance(foreground), luminance(background));
  const darker = Math.min(luminance(foreground), luminance(background));
  return (lighter + 0.05) / (darker + 0.05);
}

describe("semantic color accessibility", () => {
  it.each(["light", "dark"] as const)(
    "%s theme text and accent tokens meet WCAG AA on the primary surface",
    (theme) => {
      const surface = token(theme, "color-surface");
      const textTokens = [
        "color-ink",
        "color-ink-soft",
        "color-text",
        "color-text-soft",
        "color-muted",
        "color-muted-soft",
        "color-stone",
        "color-stone-light",
        "color-teal",
        "color-indigo",
        "color-amber",
        "color-red",
      ];

      const failures = textTokens
        .map((name) => ({ name, ratio: contrast(token(theme, name), surface) }))
        .filter(({ ratio }) => ratio < 4.5);

      expect(failures).toEqual([]);
    },
  );
});

describe("essential metadata typography", () => {
  it("uses the readable text token instead of sub-12px literals", () => {
    const files = ["pages.css", "components.css", "cbom.css", "redesign.css", "auth.css"];
    const failures = files.flatMap((file) => {
      const css = readFileSync(resolve(process.cwd(), `src/styles/${file}`), "utf8");
      return [...css.matchAll(/font-size:\s*(8(?:\.5)?|9(?:\.5)?|10(?:\.5)?)px\s*;/g)].map(
        (match) => `${file}:${match[0]}`,
      );
    });

    expect(failures).toEqual([]);
  });
});
