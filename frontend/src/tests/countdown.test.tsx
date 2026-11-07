import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { formatClock } from "../components/common";

describe("formatClock", () => {
  it("formats server countdown values", () => {
    expect(formatClock(1440)).toBe("24:00");
    expect(formatClock(0)).toBe("00:00");
    expect(formatClock(-4)).toBe("00:00");
  });
});
