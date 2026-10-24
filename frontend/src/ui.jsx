import { useEffect, useState } from "react";

/** Run an async loader whenever deps change; ignores stale responses. */
export function useAsync(loader, deps) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    loader()
      .then((data) => live && setState({ loading: false, data, error: null }))
      .catch((error) => live && setState({ loading: false, data: null, error }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function Kpi({ label, value, hint }) {
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export function Status({ state, children }) {
  if (state.loading && !state.data) return <div className="loading">Loading…</div>;
  if (state.error) return <div className="banner err">Could not load data: {state.error.message}</div>;
  return children(state.data);
}

export function Legend({ items }) {
  return (
    <div className="legend">
      {items.map((it) => (
        <span key={it.label}>
          <i className={it.box ? "swatch" : ""} style={{ background: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

/** Generic recharts tooltip: rows = [{label, value}] built by `build(payloadPoint)`. */
export function Tip({ active, payload, title, build }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tooltip">
      <div className="t">{title(p)}</div>
      {build(p).map((r) => (
        <div className="r" key={r.label}><span>{r.label}</span><b>{r.value}</b></div>
      ))}
    </div>
  );
}

export function TableView({ columns, rows, summary = "Show as table" }) {
  return (
    <details className="table-view">
      <summary>{summary}</summary>
      <div className="scroll">
        <table className="data">
          <thead><tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>{columns.map((c) => <td key={c.key}>{c.fmt ? c.fmt(r[c.key], r) : r[c.key]}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
