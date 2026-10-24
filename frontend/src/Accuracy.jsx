import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";
import { fmtDateTime, fmtDay, mw, num, pct, signed } from "./format";
import { Kpi, Legend, Status, TableView, Tip, useAsync } from "./ui";

const AXIS = { stroke: "var(--muted)", fontSize: 12 };
const xAxisProps = { ...AXIS, tickLine: false, axisLine: { stroke: "var(--axis)" } };
const yAxisProps = { ...AXIS, tickLine: false, axisLine: false, width: 48 };

export default function Accuracy({ start, end, cutoff }) {
  const state = useAsync(() => api.accuracy(start, end, cutoff), [start, end, cutoff]);
  return <Status state={state}>{(a) => <Body a={a} />}</Status>;
}

function Body({ a }) {
  const o = a.overall;
  if (!o.n) return <div className="banner warn">No overlapping forecast/actual data for this range.</div>;

  const biasWord = o.bias > 0 ? "over-forecasts" : "under-forecasts";
  return (
    <>
      <p className="takeaway">
        Using the forecast available at {a.cutoff_local} UK the day before, wind output was off by{" "}
        <b>{mw(o.mae)}</b> on average ({pct(o.wape_pct)} of generation). Nine times in ten the miss was under{" "}
        <b>{mw(o.p90_abs)}</b>; the worst single point missed by {mw(o.max_abs)}. The forecast on average{" "}
        {biasWord} by {mw(Math.abs(o.bias))}.
      </p>

      <div className="grid kpis">
        <Kpi label="MAE" value={mw(o.mae)} hint="mean absolute error" />
        <Kpi label="RMSE" value={mw(o.rmse)} hint="penalises big misses" />
        <Kpi label="Bias" value={`${signed(o.bias)} MW`} hint="forecast − actual; + = over" />
        <Kpi label="WAPE" value={pct(o.wape_pct)} hint="Σ|error| / Σ actual" />
        <Kpi label="P90 abs error" value={mw(o.p90_abs)} hint={`P95 ${mw(o.p95_abs)}`} />
        <Kpi label="Points scored" value={num(o.n)} hint={`${a.start} → ${a.end}`} />
      </div>

      <div className="card" style={{ marginBottom: 12 }}>
        <h2>Forecast vs actual</h2>
        <p className="desc">Decision-time forecast against what was generated, whole period.</p>
        <Legend items={[{ label: "Forecast (known at cutoff)", color: "var(--series-1)" }, { label: "Actual", color: "var(--series-2)" }]} />
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={a.timeseries} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="t" tickFormatter={fmtDay} minTickGap={48} {...xAxisProps} />
            <YAxis tickFormatter={(v) => `${v / 1000}`} {...yAxisProps}
              label={{ value: "GW", angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 12 }} />
            <Tooltip content={<Tip
              title={(p) => fmtDateTime(p.t)}
              build={(p) => [
                { label: "Forecast", value: mw(p.forecast) },
                { label: "Actual", value: mw(p.actual) },
              ]} />} />
            <Line dataKey="actual" stroke="var(--series-2)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            <Line dataKey="forecast" stroke="var(--series-1)" strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid two">
        <div className="card">
          <h2>Daily error</h2>
          <p className="desc">MAE per delivery day (MW) – spot the days the forecast struggled.</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={a.by_day} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="date" tickFormatter={fmtDay} minTickGap={24} {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip cursor={{ fill: "var(--grid)", opacity: 0.5 }} content={<Tip
                title={(p) => fmtDay(p.date)}
                build={(p) => [
                  { label: "MAE", value: mw(p.mae) }, { label: "RMSE", value: mw(p.rmse) },
                  { label: "Bias", value: `${signed(p.bias)} MW` }, { label: "Avg actual", value: mw(p.mean_actual) },
                ]} />} />
              <Bar dataKey="mae" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
          <TableView columns={[
            { key: "date", label: "Day" }, { key: "mae", label: "MAE", fmt: num }, { key: "rmse", label: "RMSE", fmt: num },
            { key: "bias", label: "Bias", fmt: signed }, { key: "mean_actual", label: "Avg actual", fmt: num },
          ]} rows={a.by_day} />
        </div>

        <div className="card">
          <h2>How the error is distributed</h2>
          <p className="desc">Count of scored points by signed error (1 GW bins). Left of zero = under-forecast.</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={a.histogram} margin={{ top: 8, right: 8, left: 0, bottom: 18 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="from_mw" tickFormatter={(v) => `${v / 1000}`} {...xAxisProps}
                label={{ value: "error, GW (forecast − actual)", position: "insideBottom", offset: -14, fill: "var(--muted)", fontSize: 12 }} />
              <YAxis {...yAxisProps} />
              <ReferenceLine x={0} stroke="var(--axis)" />
              <Tooltip cursor={{ fill: "var(--grid)", opacity: 0.5 }} content={<Tip
                title={(p) => `${signed(p.from_mw)} to ${signed(p.to_mw)} MW`}
                build={(p) => [{ label: "Points", value: num(p.count) }]} />} />
              <Bar dataKey="count" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
          <TableView columns={[
            { key: "from_mw", label: "From MW", fmt: signed }, { key: "to_mw", label: "To MW", fmt: signed },
            { key: "count", label: "Points", fmt: num },
          ]} rows={a.histogram} />
        </div>

        <div className="card">
          <h2>Error by time of day</h2>
          <p className="desc">MAE by UK hour of delivery – does it get worse at particular times?</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={a.by_hour} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="hour" tickFormatter={(h) => `${String(h).padStart(2, "0")}`} {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip cursor={{ fill: "var(--grid)", opacity: 0.5 }} content={<Tip
                title={(p) => `${String(p.hour).padStart(2, "0")}:00–${String(p.hour).padStart(2, "0")}:59`}
                build={(p) => [{ label: "MAE", value: mw(p.mae) }, { label: "Bias", value: `${signed(p.bias)} MW` }, { label: "P90 abs", value: mw(p.p90_abs) }]} />} />
              <Bar dataKey="mae" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2>Error by wind level</h2>
          <p className="desc">Calm days versus windy days – where the forecast is least reliable.</p>
          <table className="data">
            <thead><tr><th>Actual output</th><th>Points</th><th>MAE</th><th>Bias</th><th>P90 abs</th></tr></thead>
            <tbody>
              {a.by_level.map((r) => (
                <tr key={r.bucket}><td>{r.bucket}</td><td>{num(r.n)}</td><td>{num(r.mae)}</td><td>{signed(r.bias)}</td><td>{num(r.p90_abs)}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="note">Values in MW. Buckets use the actual output at each scored point.</p>
        </div>
      </div>
    </>
  );
}
