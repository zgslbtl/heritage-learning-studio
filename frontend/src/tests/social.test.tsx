import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import SocialFeedPage from "../pages/SocialFeedPage";
import type { SocialWork, StudentState } from "../types";

it("shows both design rounds and keeps T1 interactions tied to their work", async () => {
  const works: SocialWork[] = [1, 2].map((round_no) => ({
    work_id: round_no,
    work_code: `W-ROUND${round_no}`,
    round_no,
    product_name: `Classmate design ${round_no}`,
    product_category: "Badge",
    design_concept: "A cultural design",
    open_statement: "A student-authored statement",
    image_url: null,
    is_own: false,
    liked_by_me: false,
  }));
  const requested: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    requested.push(`${init?.method ?? "GET"} ${url}`);
    const payload = url.endsWith("/social-feed")
      ? { works, count: works.length }
      : url.endsWith("/portfolio")
        ? { works: [] }
        : url.endsWith("/like")
          ? { work_id: 1, liked: true }
          : { ok: true };
    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  const state: StudentState = {
    participant: { id: "student-1", class_id: 1, class_name: "Class 1" },
    run_id: "run-1",
    stage: "social_feed",
    stage_label: "Work feed",
    step: 6,
    total_steps: 6,
    completed: false,
    assessment_kind: null,
    assessment_label: null,
    active_round: null,
    server_time: new Date().toISOString(),
  };
  render(<SocialFeedPage state={state} onState={() => undefined} />);
  expect(await screen.findByText("浏览本班同学的两次创作作品")).toBeInTheDocument();
  expect(screen.getByText("Browse both designs by your classmates")).toBeInTheDocument();
  expect(screen.getByText("第一次创作 / T1")).toBeInTheDocument();
  expect(screen.getByText("第二次创作 / T2")).toBeInTheDocument();
  expect(screen.getByText("Classmate design 1")).toBeInTheDocument();
  expect(screen.getByText("Classmate design 2")).toBeInTheDocument();
  await userEvent.setup().click(screen.getAllByRole("button", { name: "♡ 喜欢 / Like" })[0]);
  await waitFor(() => expect(screen.getByRole("button", { name: "♥ 已赞 / Liked" })).toBeInTheDocument());
  expect(requested).toContain("POST /api/student/social/works/1/like");
});
