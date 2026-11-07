import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import EntryPage from "../pages/EntryPage";

describe("EntryPage", () => {
  it("submits the PolyU email and selected class", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (path) => path === "/api/auth/config"
      ? new Response(JSON.stringify({ deployment_mode: "beta", classes: [{ id: 0, name: "班级0 / Internal testing" }] }))
      :
      new Response(
        JSON.stringify({
          state: {
            participant: { id: "p", class_id: 1, class_name: "Class 1" },
            run_id: "r",
            stage: "k0",
            stage_label: "K0",
            step: 1,
            total_steps: 6,
            completed: false,
            assessment_kind: "k0",
            assessment_label: "K0",
            active_round: null,
            server_time: new Date().toISOString(),
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const onEnter = vi.fn();
    render(<EntryPage onEnter={onEnter} />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("PolyU email"), "student@polyu.edu.hk");
    await waitFor(() => expect(screen.getByRole("button", { name: /开始创作/ })).toBeEnabled());
    expect(screen.getAllByRole("option")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: /开始创作/ }));
    expect(onEnter).toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/enter",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
    const submitted = fetchMock.mock.calls.find(([path]) => path === "/api/auth/enter");
    expect(JSON.parse(String(submitted?.[1]?.body)).class_id).toBe(0);
  });
});
