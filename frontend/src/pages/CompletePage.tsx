import React from "react";
import { api, errorMessage } from "../api";
import type { PortfolioWork, StudentState } from "../types";
import { BrandMark, clearLocalStudyData, ErrorNotice, Spinner } from "../components/common";
import { preparePortfolioPdf } from "../lib/portfolioPdf";

export default function CompletePage({ state }: { state: StudentState }) {
  const [loggingOut, setLoggingOut] = React.useState(false);
  const [works, setWorks] = React.useState<PortfolioWork[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [preparing, setPreparing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = React.useState<string | null>(null);
  const [textUrl, setTextUrl] = React.useState<string | null>(null);
  const portfolioRef = React.useRef<HTMLDivElement>(null);
  const urls = React.useRef<{ pdf?: string; text?: string }>({});
  const fileBase = `hlsf-portfolio-${state.participant.id.slice(0, 8)}`;

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await api<{ works: PortfolioWork[] }>("/api/student/portfolio", { cache: "no-store" });
      setWorks(data.works);
    } catch (err) { setError(errorMessage(err)); }
    finally { setLoading(false); }
  }, [state.run_id]);

  React.useEffect(() => { void load(); }, [load]);
  React.useEffect(() => () => {
    for (const url of Object.values(urls.current)) if (url) URL.revokeObjectURL(url);
  }, []);
  React.useEffect(() => {
    if (urls.current.text) URL.revokeObjectURL(urls.current.text);
    if (!works.length) { setTextUrl(null); return; }
    const text = works.map(work => [
      work.round_no === 1 ? "第一次创作 / Round 1" : "第二次创作 / Round 2",
      work.product_name, work.artifact_title,
      `类别 / Category: ${work.product_category}`, `受众 / Audience: ${work.target_audience}`,
      work.design_concept, work.statement,
    ].filter(Boolean).join("\n\n")).join("\n\n====================\n\n");
    const url = URL.createObjectURL(new Blob(["\uFEFF", text], { type: "text/plain;charset=utf-8" }));
    urls.current.text = url; setTextUrl(url);
  }, [works]);

  async function preparePdf() {
    if (!portfolioRef.current || !works.length) return;
    setPreparing(true); setError(null);
    try {
      const blob = await preparePortfolioPdf(portfolioRef.current);
      if (urls.current.pdf) URL.revokeObjectURL(urls.current.pdf);
      const url = URL.createObjectURL(blob); urls.current.pdf = url; setPdfUrl(url);
    } catch (err) { setError(errorMessage(err)); }
    finally { setPreparing(false); }
  }

  async function logout() {
    setLoggingOut(true);
    try { await api("/api/auth/logout", { method: "POST" }); }
    finally { clearLocalStudyData(); window.location.href = "/"; }
  }

  return (
    <div className="app-shell completed-download-page">
      <header className="topbar"><BrandMark /><div className="topbar-spacer" /><span className="step-badge">已完成 / Complete</span></header>
      <main className="completed-download-layout">
        <section className="panel completed-download-intro">
          <h1>作品下载<span className="en">Download your designs</span></h1>
          <p>你的任务已完成，作答和作品已保存。以后使用原班级和同一邮箱登录，会直接回到此下载页。
            <span className="en">Your study is complete and your work is saved. Sign in again with the same class and email to return directly to this download page.</span></p>
          <p className="small muted">{state.participant.class_name} · 匿名编号 / Anonymous ID: {state.participant.id.slice(0, 8).toUpperCase()}</p>
          <div className="button-row completed-download-actions" data-download-control>
            <button type="button" className="button button-primary" onClick={() => void preparePdf()} disabled={loading || preparing || !works.length}>
              {preparing ? "正在生成PDF… / Preparing PDF…" : "生成作品PDF / Prepare portfolio PDF"}
            </button>
            {pdfUrl ? <a className="button button-primary" href={pdfUrl} download={`${fileBase}.pdf`}>下载作品PDF / Download PDF</a> : null}
            <button type="button" className="button" onClick={() => window.print()} disabled={!works.length}>打印／另存为PDF / Print / Save as PDF</button>
            {textUrl ? <a className="button" href={textUrl} download={`${fileBase}.txt`}>下载作品说明 / Download statements</a> : null}
          </div>
          <p className="small muted" data-download-control>生成后请点击“下载作品PDF”。如浏览器无法保存，可使用打印另存PDF，或分别下载下方原图和作品说明。
            <span className="en">After preparation, click Download PDF. If saving is blocked, use Print / Save as PDF, or download the original images and statements separately.</span></p>
          {error ? <ErrorNotice message={error} onRetry={() => void load()} /> : null}
        </section>
        {loading ? <Spinner label="正在读取已保存作品… / Loading your saved designs…" /> : null}
        {!loading && !works.length && !error ? <div className="notice notice-info">暂无已保存作品，请联系研究者。 / No saved designs were found. Please contact the researcher.</div> : null}
        <div ref={portfolioRef} className="completed-portfolio">
          {works.map(work => <article className="portfolio-card completed-work-card" data-portfolio-card key={work.round_no}>
            <div className="portfolio-round">{work.round_no === 1 ? "第一次创作 / Round 1" : "第二次创作 / Round 2"}</div>
            <h2>{work.product_name || "未命名作品 / Untitled work"}</h2>
            {work.artifact_title ? <p>{work.artifact_title}</p> : null}
            {work.image_url ? <><img src={work.image_url} alt={work.product_name} />
              <p data-download-control><a className="button button-small" href={`${work.image_url}${work.image_url.includes("?") ? "&" : "?"}variant=original&download=1`} download>下载本轮原图 / Download original image</a></p></> : <p className="muted">未保存图片 / No saved image</p>}
            {work.product_category ? <p>类别 / Category: {work.product_category}</p> : null}
            {work.target_audience ? <p>受众 / Audience: {work.target_audience}</p> : null}
            {work.design_concept ? <p>设计概念 / Design concept: {work.design_concept}</p> : null}
            <p className="portfolio-statement">{work.statement || "未填写作品说明 / No statement provided"}</p>
          </article>)}
        </div>
        <div className="completed-download-footer" data-download-control><button type="button" className="button" onClick={() => void logout()} disabled={loggingOut}>退出账号 / Sign out</button>
          <p className="small muted">可以安全关闭页面；以后仍可用原账号回来下载。 / You may close this page and sign in again later to download.</p></div>
      </main>
    </div>
  );
}
