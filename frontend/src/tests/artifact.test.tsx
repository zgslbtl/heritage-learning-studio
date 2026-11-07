import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ArtifactReader from "../components/ArtifactReader";
import type { Artifact } from "../types";

const artifact: Artifact = {
  id: "artifact-1",
  title: "明代鹭鸶方补",
  era: "明代",
  type: "方补",
  introduction: "",
  facts: [],
  evidence: [],
  uncertainty: [],
  image_url: "/api/files/artifacts/artifact-1/image",
  sections: [
    {
      key: "overview",
      title: "总览与证据层次",
      body: "总览内容。",
      source_ids: [],
      media_keys: [],
    },
    {
      key: "M01",
      title: "M01 · 物件与可观察图像",
      body: "馆藏登记与图像观察。",
      source_ids: ["HKPM-P"],
      media_keys: [],
    },
  ],
  media: [
    {
      key: "M-full",
      caption: "馆藏登记图",
      alt: "文物图片",
      url: "/api/files/artifacts/artifact-1/media/M-full",
      original_url: "/api/files/artifacts/artifact-1/media/M-full?variant=original",
      mime: "image/jpeg",
    },
  ],
};

describe("ArtifactReader", () => {
  it("expands a section and logs open/close events with metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    render(<ArtifactReader artifact={artifact} roundNo={1} disabled={false} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /M01/ }));
    expect(screen.getByText("馆藏登记与图像观察。")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const openCall = fetchMock.mock.calls.find(([url, init]) => {
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      return String(url).includes("evidence-events") && body?.event_type === "section_open";
    });
    expect(openCall).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /M01/ }));
    await waitFor(() => {
      const closeCall = fetchMock.mock.calls.find(([url, init]) => {
        const body = init?.body ? JSON.parse(String(init.body)) : null;
        return String(url).includes("evidence-events") && body?.event_type === "section_close";
      });
      expect(closeCall).toBeTruthy();
    });
  });
});
