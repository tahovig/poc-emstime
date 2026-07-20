import "./MetricsCard.css";

interface Props {
  label: string;
  value: string;
}

export default function MetricsCard({ label, value }: Props) {
  return (
    <div className="metrics-card">
      <div className="metrics-card__label">{label}</div>
      <div className="metrics-card__value">{value}</div>
    </div>
  );
}
