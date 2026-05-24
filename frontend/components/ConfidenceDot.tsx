type Props = {
  value: number | null | undefined;
};

export function ConfidenceDot({value}: Props) {
  const v = value ?? 0;
  const color = v >= 0.85 ? "bg-emerald-500" : v >= 0.6 ? "bg-amber-500" : "bg-red-500";
  const label = v >= 0.85 ? "ثقة عالية" : v >= 0.6 ? "ثقة متوسطة" : "ثقة منخفضة";
  return (
    <span className="inline-flex items-center gap-2 text-xs text-slate-600" title={`${label} (${(v * 100).toFixed(0)}%)`}>
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} aria-hidden="true" />
      {label} ({(v * 100).toFixed(0)}%)
    </span>
  );
}
