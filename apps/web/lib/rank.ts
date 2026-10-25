/** Kyu/dan scale shared with the backend (`humansl_bot.rank_label`): 25 -> "25k", 0 -> "1d". */
export function rankLabel(rank: number): string {
  const r = Math.round(rank);
  return r >= 1 ? `${r}k` : `${1 - r}d`;
}
