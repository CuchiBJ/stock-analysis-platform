type GroupStrengthBadgeProps = {
  group: string | null | undefined
  badge: 'leader' | 'neutral' | 'weak' | string | undefined
  rank?: number | null
  totalGroups?: number
}

export default function GroupStrengthBadge({ group, badge, rank, totalGroups = 25 }: GroupStrengthBadgeProps) {
  if (!badge || badge === 'neutral' || !group) return null

  const tooltip = rank != null
    ? `${group} · #${rank} of ${totalGroups}`
    : group

  if (badge === 'leader') {
    return (
      <span
        title={tooltip}
        className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium uppercase tracking-wide bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 cursor-default"
      >
        🔥 Group leader
      </span>
    )
  }

  if (badge === 'weak') {
    return (
      <span
        title={tooltip}
        className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-medium uppercase tracking-wide bg-amber-500/20 text-amber-400 border border-amber-500/30 cursor-default"
      >
        ⚠️ Weak group
      </span>
    )
  }

  return null
}
