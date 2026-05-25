import React from "react";

// Backend returns citations whose marker text is "¶N" (Arabic-Indic or
// western digits). The reply text may use either set inline. This module
// owns the parsing and rendering so HomeShell and DocumentShell don't
// duplicate it.

export type Citation = {
  marker: string;
  doc_id: string;
  chunk_id: string;
  paragraph_no: number | null;
  quoted_text_ar: string;
  title_ar?: string;
  doc_type?: string;
  source_url?: string | null;
};

const AR_DIGIT_MAP = "٠١٢٣٤٥٦٧٨٩";

function toWesternDigits(s: string): string {
  return s.replace(/[٠-٩]/g, (d) => String(AR_DIGIT_MAP.indexOf(d)));
}

/** Render answer text with [¶N] markers replaced by clickable chips.
 *  onCitationClick receives the paragraph_no and the matching Citation
 *  (if any) so the caller can decide what to do (scroll, navigate, etc.). */
export function renderAnswerWithCitationChips(
  answer: string,
  citations: Citation[],
  onCitationClick: (n: number, cited: Citation | undefined) => void,
): React.ReactNode {
  if (!answer) return null;
  const parts: (string | {marker: string; n: number})[] = [];
  const re = /\[¶([0-9٠-٩]+)\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(answer)) !== null) {
    if (m.index > last) parts.push(answer.slice(last, m.index));
    const n = parseInt(toWesternDigits(m[1]), 10);
    parts.push({marker: m[0], n});
    last = re.lastIndex;
  }
  if (last < answer.length) parts.push(answer.slice(last));

  return parts.map((p, i) => {
    if (typeof p === "string") return <span key={i}>{p}</span>;
    const cited = citations.find((c) => c.paragraph_no === p.n);
    return (
      <button
        key={i}
        type="button"
        className="mx-1 rounded bg-teal-100 px-1.5 py-0.5 text-xs font-semibold text-teal-900 hover:bg-teal-200"
        onClick={() => onCitationClick(p.n, cited)}
        title={cited?.quoted_text_ar ?? ""}
      >
        {p.marker}
      </button>
    );
  });
}
