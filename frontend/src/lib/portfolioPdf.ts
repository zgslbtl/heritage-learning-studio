const PREPARATION_TIMEOUT = "作品PDF准备超时，请重试，或使用打印另存PDF。 / PDF preparation timed out. Retry or use Print / Save as PDF.";

export function within<T>(promise: Promise<T>, milliseconds: number, message = PREPARATION_TIMEOUT): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(message)), milliseconds);
    promise.then(value => { window.clearTimeout(timer); resolve(value); }, error => { window.clearTimeout(timer); reject(error); });
  });
}

export async function waitForPortfolioImages(root: HTMLElement): Promise<void> {
  await Promise.all(Array.from(root.querySelectorAll("img")).map(image => new Promise<void>((resolve, reject) => {
    let timer: number | undefined;
    const finish = () => {
      window.clearTimeout(timer);
      image.removeEventListener("load", loaded); image.removeEventListener("error", failed);
    };
    const loaded = () => { finish(); image.naturalWidth > 0 ? resolve() : failed(); };
    const failed = () => { finish(); reject(new Error("作品图片暂未加载，请重试，或单独下载原图。 / An image could not load. Retry or download the original separately.")); };
    if (image.complete) { image.naturalWidth > 0 ? resolve() : failed(); return; }
    image.addEventListener("load", loaded, { once: true }); image.addEventListener("error", failed, { once: true });
    timer = window.setTimeout(() => { finish(); reject(new Error(PREPARATION_TIMEOUT)); }, 15000);
  })));

}

/** Prepare a Blob; a separate user click saves it, avoiding lost download gestures. */
export async function preparePortfolioPdf(root: HTMLElement): Promise<Blob> {
  const cards = Array.from(root.querySelectorAll<HTMLElement>("[data-portfolio-card]"));
  if (!cards.length) throw new Error("暂无可导出的作品。 / No works are available to export.");
  const [{ default: html2canvas }, { jsPDF }] = await within(Promise.all([import("html2canvas"), import("jspdf")]), 20000);
  await waitForPortfolioImages(root);
  if (document.fonts?.ready) await within(Promise.resolve(document.fonts.ready), 10000);
  const pdf = new jsPDF({ unit: "mm", format: "a4", orientation: "portrait" });
  let pages = 0;
  for (const card of cards) {
    const width = Math.max(1, card.scrollWidth), height = Math.max(1, card.scrollHeight);
    // Bound canvas memory on phones and paginate long statements instead of
    // compressing a whole tall card onto one unreadable page.
    const scale = Math.min(1.5, 1800 / width, Math.sqrt(4_000_000 / (width * height)));
    const canvas = await within(html2canvas(card, { scale, backgroundColor: "#ffffff", useCORS: true,
      imageTimeout: 15000, logging: false, ignoreElements: element => element.hasAttribute("data-download-control") }), 30000);
    if (!canvas.width || !canvas.height) throw new Error("作品渲染失败，请使用打印另存PDF。 / Rendering failed. Use Print / Save as PDF.");
    const sliceHeight = Math.max(1, Math.floor(canvas.width * 277 / 190));
    for (let top = 0; top < canvas.height; top += sliceHeight) {
      const slice = document.createElement("canvas"); slice.width = canvas.width; slice.height = Math.min(sliceHeight, canvas.height - top);
      const context = slice.getContext("2d"); if (!context) throw new Error("浏览器无法生成PDF，请使用打印另存PDF。 / Use Print / Save as PDF in this browser.");
      context.drawImage(canvas, 0, top, canvas.width, slice.height, 0, 0, slice.width, slice.height);
      if (pages++) pdf.addPage();
      pdf.addImage(slice.toDataURL("image/jpeg", 0.9), "JPEG", 10, 10, 190, 190 * slice.height / slice.width);
      slice.width = slice.height = 1;
    }
    canvas.width = canvas.height = 1;
  }
  return pdf.output("blob");
}
