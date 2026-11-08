import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ClassGatePanel from "../components/ClassGatePanel";
import type { ClassEntryLink } from "../types";

const gates = [0, 1, 2].map((classId) => ({
  class_id: classId, class_name: `班级 ${classId} / Class ${classId}`,
  status: "collecting", entered: 0, t2_ended: 0, valid_work_count: 0,
  can_open: false, batch_id: null, last_event: null,
}));

function mockServer(initial: ClassEntryLink[] = []) {
  const links = [...initial];
  let sequence = links.length;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    let data: unknown;
    if (path === "/api/admin/class-peer-gates") data = { classes: gates };
    else if (path === "/api/admin/class-links" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      const id = `link-${++sequence}`;
      const url = `https://study.example/join?token=${id}`;
      links.push({ id, class_id: body.class_id, label: body.label, active: true, url,
        created_at: "2026-11-09T00:00:00Z", revoked_at: null });
      data = { url };
    } else if (path === "/api/admin/class-links") data = { links };
    else throw new Error(`Unexpected request: ${path}`);
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  return links;
}

describe("saved class entry links", () => {
  it("retains and copies each class URL after generating another class and remounting", async () => {
    mockServer();
    const user = userEvent.setup();
    const copy = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    const view = render(<ClassGatePanel />);
    await screen.findByRole("button", { name: /生成链接/ });
    await user.click(screen.getByRole("button", { name: /生成链接/ }));
    const first = "https://study.example/join?token=link-1";
    expect(await screen.findByDisplayValue(first)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Class for link"), "2");
    await user.click(screen.getByRole("button", { name: /生成链接/ }));
    const second = "https://study.example/join?token=link-2";
    expect(await screen.findByDisplayValue(second)).toBeInTheDocument();
    expect(screen.getByDisplayValue(first)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Copy Class 1 link/ }));
    expect(copy).toHaveBeenCalledWith(first);
    view.unmount();
    render(<ClassGatePanel />);
    expect(await screen.findByDisplayValue(first)).toBeInTheDocument();
    expect(screen.getByDisplayValue(second)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /刷新/ }));
    await waitFor(() => expect(screen.getByDisplayValue(first)).toBeInTheDocument());
    expect(screen.getByDisplayValue(second)).toBeInTheDocument();
  });

  it("offers regeneration for a legacy URL without showing a misleading link", async () => {
    mockServer([{ id: "older", class_id: 1, label: "Older link", active: true, url: null,
      created_at: "2026-11-08T00:00:00Z", revoked_at: null }]);
    render(<ClassGatePanel />);
    expect(await screen.findByText(/旧版链接无法再次显示/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /重新生成/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Copy Class 1 link/ })).not.toBeInTheDocument();
  });
});
