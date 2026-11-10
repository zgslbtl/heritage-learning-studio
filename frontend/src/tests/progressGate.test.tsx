import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AdminOverview, { type OverviewData } from "../components/AdminOverview";
import StudentApp from "../pages/StudentApp";
import PeerAssessmentPage from "../pages/PeerAssessmentPage";
import type { PeerPayload, StudentState } from "../types";

const state: StudentState = { participant: { id: "p1", class_id: 1, class_name: "Class 1" }, run_id: "r1", stage: "peer_assessment", stage_label: "Peer assessment", step: 6, total_steps: 6, completed: false, assessment_kind: null, assessment_label: null, active_round: null, server_time: "2026-11-10T06:00:00Z" };
const gate = { class_id: 1, class_name: "Class 1", status: "collecting" as const, entered: 30, active_count: 30, ready_count: 26, completion_percent: 86.7, t2_ended: 29, valid_work_count: 58, can_open: false, message: "等待至少90%完成", message_en: "Waiting for at least 90% ready", timer_started_at: "2026-11-10T05:01:00Z", remaining_seconds: 60, batch_id: null, last_event: null };
function mockApi(data: OverviewData | null = null, stopped = false) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const path = String(input);
    const body = path === "/api/admin/class-peer-gates" ? { classes: [gate] }
      : path === "/api/admin/class-links" ? { links: [] }
      : path === "/api/student/state" ? { ...state, stopped }
      : path === "/api/student/peer-assessment" ? { waiting: true, gate, batch: null, assignments: [], completed: false, submitted: 0, total: 0 } satisfies PeerPayload
      : path.endsWith("/stop") && init?.method === "POST" ? { stopped: true }
      : data;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

describe("progress gates", () => {
  it("shows bilingual readiness and countdown without altering review controls", async () => {
    mockApi(); render(<PeerAssessmentPage state={state} onState={vi.fn()} />);
    expect(await screen.findByText("等待本班开放互评")).toBeInTheDocument();
    expect(screen.getByText(/86.7%/)).toBeInTheDocument();
    expect(screen.getByText(/Time remaining: 1 min/)).toBeInTheDocument();
    expect(screen.getByText("Waiting for at least 90% ready")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Continue/ })).not.toBeInTheDocument();
  });
  it("requires a reason and explicit confirmation for a specific participant", async () => {
    const data = { readiness: { ready_for_students: true, deployment_mode: "study", ready_to_activate: true, checks: [], active_protocol: null, latest: { artifacts: {}, instruments: {} }, participant_count: 1, run_count: 1, demo_present: false }, protocol: null, participants: [{ participant_id: "p1", class_id: 1, class_name: "Class 1", group: "G1", email: "test@polyu.edu.hk", code_last4: null, run_id: "r1", stage: "k3", stage_label: "K3", step: 5, last_activity_at: null, completed_at: null, completed: false, can_stop: true }], counts: { participants: 1, started: 1, completed: 0, by_stage: { k3: 1 }, by_group: { G1: 1 } }, server_time: state.server_time } as OverviewData;
    const fetch = mockApi(data); const refresh = vi.fn(); const user = userEvent.setup();
    render(<AdminOverview data={data} onSelectParticipant={vi.fn()} onRefresh={refresh} />);
    await user.click(screen.getByRole("button", { name: "停止任务 / Stop" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("test@polyu.edu.hk");
    const confirm = screen.getByRole("button", { name: "确认 / Confirm" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByLabelText("操作原因 / Reason"), "本人确认退出课堂");
    await user.click(confirm);
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
    const calls = fetch.mock.calls.filter(([path]) => String(path).endsWith("/stop"));
    expect(calls).toHaveLength(1);
    expect(JSON.parse(String(calls[0][1]?.body))).toEqual({ reason: "本人确认退出课堂" });
  });
  it("shows the stopped screen in place of task forms", async () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    mockApi(null, true); render(<StudentApp />);
    expect(await screen.findByText("任务已由管理员停止")).toBeInTheDocument();
    expect(screen.getByText("Your task has been stopped by the researcher")).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });
});
