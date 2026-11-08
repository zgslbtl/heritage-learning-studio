import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import AssessmentPage from "../pages/AssessmentPage";
import type { AssessmentPayload, Question, StudentState } from "../types";
import content from "./fixtures/survey_v3.json";

it("renders bilingual V3, saves zero, retains answers on back navigation and submits S1–S19", async () => {
  const state = { run_id: "v3-run", step: 5, stage: "survey" } as StudentState;
  const payload: AssessmentPayload = {
    instrument: { ...content, id: "v3", kind: "survey", version: 3, questions: content.questions as Question[] },
    answers: {}, status: "draft", started_at: null, updated_at: null,
  };
  let submitted: Record<string, unknown> | undefined;
  let draft: Record<string, unknown> | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/survey/submit")) submitted = JSON.parse(String(init?.body)).answers;
    if (url.endsWith("/survey/draft")) draft = JSON.parse(String(init?.body)).answers;
    return new Response(JSON.stringify(url.endsWith("/submit") ? { state: { ...state, stage: "peer_assessment" } } : payload), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  const user = userEvent.setup();
  const onState = vi.fn();
  render(<AssessmentPage state={state} kind="survey" onState={onState} />);
  expect(await screen.findByRole("heading", { name: content.title })).toBeInTheDocument();
  expect(screen.getByText(content.title_en)).toBeInTheDocument();
  expect(screen.getByText("Part 1: Round 1 creation")).toBeInTheDocument();
  expect(screen.queryByTestId("question-S10")).not.toBeInTheDocument();
  expect(screen.queryByText(/反向计分/)).not.toBeInTheDocument();
  const first = within(screen.getByTestId("question-S1"));
  expect(first.getAllByRole("radio")).toHaveLength(11);
  expect(first.getByText("Strongly disagree")).toBeInTheDocument();
  expect(within(screen.getByTestId("question-S5")).getByText("Somewhat true")).toBeInTheDocument();
  expect(within(screen.getByTestId("question-S9")).getByText("Moderate")).toBeInTheDocument();
  await user.click(first.getAllByRole("radio")[0]);
  await waitFor(() => expect(draft?.S1).toBe(0), { timeout: 2500 });
  await user.click(screen.getByRole("button", { name: "继续 / Continue" }));
  expect(screen.getByText(/Some questions are still unanswered/)).toBeInTheDocument();
  for (let i = 2; i <= 9; i++) await user.click(within(screen.getByTestId(`question-S${i}`)).getAllByRole("radio")[0]);
  await user.click(screen.getByRole("button", { name: "继续 / Continue" }));
  expect(screen.getByText("Part 2: Round 2 creation")).toBeInTheDocument();
  expect(within(screen.getByTestId("question-S10")).getAllByRole("radio")).toHaveLength(11);
  expect(within(screen.getByTestId("question-S14")).getAllByRole("radio")).toHaveLength(7);
  expect(within(screen.getByTestId("question-S18")).getAllByRole("radio")).toHaveLength(9);
  await user.click(screen.getByRole("button", { name: "返回 / Back" }));
  expect(within(screen.getByTestId("question-S1")).getAllByRole("radio")[0]).toBeChecked();
  await user.click(screen.getByRole("button", { name: "继续 / Continue" }));
  for (let i = 10; i <= 18; i++) await user.click(within(screen.getByTestId(`question-S${i}`)).getAllByRole("radio")[0]);
  await user.click(screen.getByRole("button", { name: "继续 / Continue" }));
  expect(screen.getByText("Part 3: Overall preference")).toBeInTheDocument();
  const preference = within(screen.getByTestId("question-S19"));
  expect(preference.getAllByRole("radio")).toHaveLength(4);
  expect(preference.getByText("About the same")).toBeInTheDocument();
  await user.click(preference.getAllByRole("radio")[2]);
  await user.click(screen.getByRole("button", { name: "继续 / Continue" }));
  await waitFor(() => expect(onState).toHaveBeenCalledOnce());
  expect(Object.keys(submitted!)).toHaveLength(19);
  expect(submitted?.S1).toBe(0);
  expect(submitted?.S10).toBe(0);
  expect(submitted?.S19).toBe("same");
});
