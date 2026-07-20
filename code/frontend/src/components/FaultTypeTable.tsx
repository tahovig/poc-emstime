import "./FaultTypeTable.css";

interface Props {
  byFaultType: Record<string, number>;
  windowLevelRecall: Record<string, boolean>;
}

export default function FaultTypeTable({ byFaultType, windowLevelRecall }: Props) {
  const faultTypes = Object.keys(byFaultType).sort();

  if (faultTypes.length === 0) {
    return <p className="fault-type-table__empty">No fault-type results yet.</p>;
  }

  return (
    <table className="fault-type-table">
      <thead>
        <tr>
          <th>Fault type</th>
          <th>Fraction of window flagged</th>
          <th>Caught at all</th>
        </tr>
      </thead>
      <tbody>
        {faultTypes.map((faultType) => (
          <tr key={faultType}>
            <td>{faultType}</td>
            <td>{(byFaultType[faultType] * 100).toFixed(0)}%</td>
            <td>{windowLevelRecall[faultType] ? "Yes" : "No"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
