import { afterEach, describe, expect, it, vi } from "vitest";
import { preparePortfolioPdf, waitForPortfolioImages, within } from "../lib/portfolioPdf";

afterEach(() => vi.useRealTimers());
describe("portfolio export failures", () => {
  it("times out an unresolved module/render instead of waiting forever", async () => {
    vi.useFakeTimers(); const result = within(new Promise(() => {}), 20);
    const failure = expect(result).rejects.toThrow(/timed out/);
    await vi.advanceTimersByTimeAsync(20); await failure;
  });
  it("rejects a broken image instead of silently exporting a blank image", async () => {
    const root = document.createElement("div"); root.innerHTML = '<img src="broken.png">';
    Object.defineProperty(root.querySelector('img'), 'complete', { value: true });
    await expect(waitForPortfolioImages(root)).rejects.toThrow(/image could not load/);
  });
  it("bounds slow image loading and removes event listeners", async () => {
    vi.useFakeTimers(); const root = document.createElement("div"); const image = document.createElement("img"); root.append(image);
    Object.defineProperty(image, "complete", { value: false }); const remove = vi.spyOn(image, "removeEventListener");
    const failure = expect(waitForPortfolioImages(root)).rejects.toThrow(/timed out/);
    await vi.advanceTimersByTimeAsync(15000); await failure;
    expect(remove).toHaveBeenCalledWith("load", expect.any(Function)); expect(remove).toHaveBeenCalledWith("error", expect.any(Function));
  });
  it("does not create an empty portfolio", async () => {
    await expect(preparePortfolioPdf(document.createElement("div"))).rejects.toThrow(/No works/);
  });
});
