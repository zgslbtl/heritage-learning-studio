import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import CompletePage from "../pages/CompletePage";
import StudentApp from "../pages/StudentApp";
import type { StudentState } from "../types";
import { preparePortfolioPdf } from "../lib/portfolioPdf";
vi.mock("../lib/portfolioPdf", () => ({ preparePortfolioPdf: vi.fn() }));
const state: StudentState = { participant: { id: "completed-student", class_id: 3, class_name: "Class 3" }, run_id: "completed-run", stage: "complete", stage_label: "Complete", step: 6, total_steps: 6, completed: true, assessment_kind: null, assessment_label: null, active_round: null, server_time: new Date().toISOString() };
const works = [1, 2].map(round_no => ({ round_no, artifact_title: "文物 / Artifact", product_name: `作品 ${round_no}`, product_category: "徽章", target_audience: "学生", image_url: `/api/files/keyframes/image${round_no}`, design_concept: "设计概念", statement: "已保存的文化说明" }));
function server(fail = false) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
    const path = String(input);
    if (path === "/api/student/state") return new Response(JSON.stringify(state), { status: 200 });
    if (path !== "/api/student/portfolio") throw new Error(`Unexpected request ${path}`);
    return new Response(JSON.stringify(fail ? { error: { message: "Temporary portfolio error" } } : { works }), { status: fail ? 503 : 200 });
  });
}
function urls() {
  let index = 0;
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => `blob:download-${++index}`) });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
}

describe("completed-account downloads", () => {
  it("reopens only the final download page and never requests a feed or writes progress", async () => {
    urls(); const requests = server(); vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    render(<StudentApp />);
    expect(await screen.findByText("作品下载")).toBeInTheDocument();
    expect(await screen.findByText("作品 1")).toBeInTheDocument();
    expect(screen.getByText("作品 2")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "下载本轮原图 / Download original image" })[0]).toHaveAttribute("href", "/api/files/keyframes/image1?variant=original&download=1");
    expect(requests.mock.calls.every(([path, options]) => ["/api/student/state", "/api/student/portfolio"].includes(String(path)) && (!options?.method || options.method === "GET"))).toBe(true);
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.queryByText(/浏览本班/)).not.toBeInTheDocument();
  });
  it("prepares a PDF for a separate real download click and cleans private blobs on exit", async () => {
    urls(); server(); vi.mocked(preparePortfolioPdf).mockResolvedValue(new Blob(["%PDF-1.3"], { type: "application/pdf" }));
    const view = render(<CompletePage state={state} />); await screen.findByText("作品 1");
    await userEvent.setup().click(screen.getByRole("button", { name: "生成作品PDF / Prepare portfolio PDF" }));
    const link = await screen.findByRole("link", { name: "下载作品PDF / Download PDF" });
    expect(link).toHaveAttribute("href", "blob:download-2"); expect(link).toHaveAttribute("download", "hlsf-portfolio-complete.pdf");
    view.unmount(); expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:download-2");
  });
  it("offers retry and native printing when PDF preparation fails without resetting completion", async () => {
    urls(); const requests = server(); vi.mocked(preparePortfolioPdf).mockRejectedValue(new Error("PDF failed"));
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    render(<CompletePage state={state} />); await screen.findByText("作品 1");
    const user = userEvent.setup(); await user.click(screen.getByRole("button", { name: "生成作品PDF / Prepare portfolio PDF" }));
    expect(await screen.findByText("PDF failed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "打印／另存为PDF / Print / Save as PDF" })); expect(print).toHaveBeenCalledOnce();
    expect(screen.getByRole("link", { name: "下载作品说明 / Download statements" })).toHaveAttribute("download", "hlsf-portfolio-complete.txt");
    expect(requests.mock.calls.every(([, options]) => !options?.method || options.method === "GET")).toBe(true);
  });
  it("shows a retry for failed portfolio reads", async () => {
    urls(); server(true); render(<CompletePage state={state} />);
    expect(await screen.findByText("Temporary portfolio error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /重试|Retry/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成作品PDF / Prepare portfolio PDF" })).toBeDisabled();
  });
});
