import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MessageText } from "../pages/Workbench";

describe("MessageText section references", () => {
  it("renders a known section code as a button and reports the click", async () => {
    const onSectionRef = vi.fn();
    render(
      <MessageText
        text="资料记载鹭鸶对应六品文官（M03），可以核对一下。"
        sectionKeys={new Set(["M03"])}
        onSectionRef={onSectionRef}
      />,
    );
    const chip = screen.getByRole("button", { name: "打开资料 M03" });
    expect(chip).toHaveTextContent("M03");
    await userEvent.click(chip);
    expect(onSectionRef).toHaveBeenCalledWith("M03");
  });

  it("leaves unknown section codes as plain text", () => {
    render(
      <MessageText
        text="这一段参考 M09，但本件文物没有这一节。"
        sectionKeys={new Set(["M03"])}
        onSectionRef={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /M09/ })).not.toBeInTheDocument();
    expect(screen.getByText(/这一段参考 M09/)).toBeInTheDocument();
  });

  it("does not linkify without a handler", () => {
    render(<MessageText text="见 M03。" sectionKeys={new Set(["M03"])} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("keeps bold segments working next to section chips", () => {
    render(
      <MessageText
        text="**小结**：依据在 M03。"
        sectionKeys={new Set(["M03"])}
        onSectionRef={vi.fn()}
      />,
    );
    expect(screen.getByText("小结")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打开资料 M03" })).toBeInTheDocument();
  });
});
