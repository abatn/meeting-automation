const DEFAULT_SPEAKER_COLORS = [
  "#3B82F6", "#8B5CF6", "#22C55E", "#FBBF24",
  "#EC4899", "#14B8A6", "#F97316", "#6366F1",
];

export function speakerColor(name: string, colors: string[] = DEFAULT_SPEAKER_COLORS): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

export function speakerInitial(name: string): string {
  return (name || "?").charAt(0).toUpperCase();
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
