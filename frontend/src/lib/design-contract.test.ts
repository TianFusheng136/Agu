import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const css = readFileSync(
  join(process.cwd(), "src", "app", "globals.css"),
  "utf8",
);
const overviewRoutes = [
  join(process.cwd(), "src", "app", "page.tsx"),
  join(process.cwd(), "src", "app", "sectors", "page.tsx"),
  join(process.cwd(), "src", "app", "stocks", "page.tsx"),
  join(process.cwd(), "src", "app", "brief", "page.tsx"),
].map((path) => readFileSync(path, "utf8"));
const radarViews = readFileSync(
  join(process.cwd(), "src", "components", "radar-views.tsx"),
  "utf8",
);
const radarShell = readFileSync(
  join(process.cwd(), "src", "components", "radar-shell.tsx"),
  "utf8",
);

describe("desktop design contract", () => {
  it("uses the approved 1280px focused shell", () => {
    expect(css).toContain("--shell-max: 1280px");
    expect(css).toContain("--shell-gutter: 32px");
    expect(css).toContain("--shell-gutter-right: 80px");
    expect(css).toContain("width: min(var(--shell-max), 100%)");
    expect(css).toContain(
      "padding: 0 var(--shell-gutter-right) 0 var(--shell-gutter)",
    );
  });

  it("gives frequent pressable surfaces immediate restrained feedback", () => {
    expect(css).toContain(".direction-links a:active");
    expect(css).toContain(".stock-link-row:active");
    expect(css).toContain("transform: scale(0.98)");
    expect(css).toContain(
      "transform var(--duration-fast) var(--ease-out)",
    );
  });

  it("keeps overview routes reusable instead of forcing a fresh server render on every click", () => {
    for (const route of overviewRoutes) {
      expect(route).not.toContain('dynamic = "force-dynamic"');
      expect(route).toContain("revalidate = 30");
    }
  });

  it("ships the Radar OS spatial hierarchy instead of another table-only skin", () => {
    expect(radarShell).toContain("radar-ambient");
    expect(radarShell).toContain("control-island");
    expect(radarViews).toContain("market-command-hero");
    expect(radarViews).toContain("market-pulse-orb");
    expect(radarViews).toContain("sector-atlas");
    expect(radarViews).toContain("brief-command-grid");
    expect(css).toContain("backdrop-filter: blur(28px) saturate(150%)");
  });

  it("provides restrained motion and accessibility fallbacks", () => {
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    expect(css).toContain("@media (prefers-reduced-transparency: reduce)");
    expect(css).toContain("@media (prefers-contrast: more)");
    expect(css).toContain("transform: scale(0.97)");
  });

  it("keeps recording-safe navigation and fully themed controls", () => {
    expect(css).toContain(".radar-os .control-island");
    expect(css).toContain("position: relative");
    expect(css).toContain(".llm-status__actions button");
    expect(css).toContain(".market-breadth {");
    expect(css).toContain("grid-template-columns: repeat(2, minmax(0, 1fr))");
  });
});
