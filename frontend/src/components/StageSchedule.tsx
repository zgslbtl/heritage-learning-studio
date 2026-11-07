import React from "react";
import { Bilingual } from "./common";

const STEPS = [
  { zh: "开始前", en: "Before we begin" },
  { zh: "第一次文物创作", en: "First artifact design" },
  { zh: "学习回顾", en: "A quick look back" },
  { zh: "第二次文物创作", en: "Second artifact design" },
  { zh: "最后回顾", en: "Final reflection" },
  { zh: "作品交流", en: "Peer & work feed" },
];

export function StageSchedule({ currentStep }: { currentStep: number }) {
  return (
    <aside className="schedule-card">
      <h3>
        <Bilingual zh="今天的安排" en="Today's schedule" />
      </h3>
      <p className="muted small">
        <Bilingual zh="约 94 分钟" en="≈ 94 minutes" />
      </p>
      <ol className="schedule-list">
        {STEPS.map((step, index) => (
          <li
            key={step.zh}
            className={index + 1 === currentStep ? "active" : index + 1 < currentStep ? "done" : ""}
          >
            <span className="schedule-dot">{index + 1}</span>
            <span>
              {step.zh}
              <span className="en"> {step.en}</span>
            </span>
          </li>
        ))}
      </ol>
      <div className="schedule-note">
        <Bilingual
          zh="第一次创作约 24 分钟，第二次约 20 分钟。开始后计时不会暂停。"
          en="The first design is about 24 minutes and the second about 20 minutes. The timer does not pause."
        />
      </div>
    </aside>
  );
}
