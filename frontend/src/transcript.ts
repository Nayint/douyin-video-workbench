export type TranscriptParagraph = {
  text: string;
  start?: number;
  end?: number;
};
export function transcriptParagraphs(
  text: string,
  segments: any[],
  edited: boolean,
): TranscriptParagraph[] {
  if (edited || !segments.length) {
    const parts = text
      .split(/\n\s*\n|\n/)
      .map((t) => t.trim())
      .filter(Boolean);
    return parts.flatMap((part) => {
      if (part.length <= 90) return [{ text: part }];
      const sentences = part.split(/(?<=[。！？!?])/u).filter(Boolean);
      return sentences.flatMap((sentence) =>
        Array.from(sentence.matchAll(/[\s\S]{1,80}/gu), (m) => ({
          text: m[0],
        })),
      );
    });
  }
  const result: TranscriptParagraph[] = [];
  let current: TranscriptParagraph | null = null;
  for (const segment of segments) {
    const t = String(segment.text || "").trim();
    if (!t) continue;
    if (
      current &&
      (current.text.length >= 65 ||
        Number(segment.start) - Number(current.end) > 0.8 ||
        /[。！？!?]$/.test(current.text))
    ) {
      result.push(current);
      current = null;
    }
    if (!current)
      current = {
        text: t,
        start: Number(segment.start),
        end: Number(segment.end),
      };
    else {
      current.text += " " + t;
      current.end = Number(segment.end);
    }
  }
  if (current) result.push(current);
  return result;
}
