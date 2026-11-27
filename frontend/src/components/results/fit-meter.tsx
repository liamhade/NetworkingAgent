const fitClass = (score: number) => (score >= 80 ? 'strong' : score >= 70 ? 'good' : 'fair')
const fitLabel = (score: number) =>
  score >= 80 ? 'Strong fit' : score >= 70 ? 'Good fit' : 'Possible fit'

export function FitMeter({ score }: { score: number | null | undefined }) {
  if (score == null) return null
  return (
    <span className={`fit ${fitClass(score)}`}>
      <b className="num">{score}</b>
      <span className="bar">
        <i style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
      </span>
      <small>{fitLabel(score)}</small>
    </span>
  )
}
