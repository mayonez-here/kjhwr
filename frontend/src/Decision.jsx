import { useMemo } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";
import { fmtDateTime, fmtDay, fmtTime, gw, mw, num, signed } from "./format";
import { Kpi, Legend, Status, TableView, Tip, useAsync } from "./ui";

const AXIS = { stroke: "var(--muted)", fontSize: 12 };

export default function Decision({ meta, day, cutoff }) {
  const state = useAsync(() => api.decision(day, cutoff), [day, cutoff]);
  return <Status state={state}>{(d) => <Body d={d} />}</Status>;
}

function Body({ d }) {
  const s = d.summary;
  const hasBand = !!d.band;
  const data = useMemo(
    () => d.series.map((p) => ({
      ...p,
      bandBase: p.lower,
      bandSize: p.lower != null && p.upper != null ? p.upper - p.lower : null,
    })),
    [d],
  );
  const delivered = d.series.some((p) => p.actual != null);

  return (
    <>
      <p className="takeaway">
        Delivery <b>{fmtDay(d.series[0].t)}</b>: wind is forecast to average <b>{mw(s.avg_mw)}</b>
        {s.energy_mwh != null && <> (≈ {num(s.energy_mwh)} MWh over the day)</>}.
        {hasBand && s.downside_gap_mw != null && (
          <> Based on recent errors, plan for it to come in <b>up to {mw(s.downside_gap_mw)}</b> lower on average
            (80% interval) – that is the extra firm power to have a plan for.</>
        )}
        {!hasBand && <> Not enough earlier days to size the uncertainty band for this date.</>}
      </p>

      <div className="grid kpis">
        <Kpi label="Avg forecast wind" value={gw(s.avg_mw)} hint={`min ${gw(s.min_mw)} · max ${gw(s.max_mw)}`} />
        <Kpi label="Downside avg (P10 actual)" value={hasBand ? gw(s.downside_avg_mw) : "–"} hint="forecast minus P90 of recent error" />
        <Kpi label="Latest forecast used" value={fmtDateTime(d.forecast_runs.latest_publish)} hint={`gate closure ${d.cutoff_local} UK, ${d.forecast_runs.distinct_runs} run(s) blended`} />
        <Kpi label="Coverage" value={`${d.coverage.points}/${d.coverage.expected}`} hint="time slots with a forecast" />
        {d.realised && <Kpi label="This day's realised MAE" value={mw(d.realised.mae)} hint={`bias ${signed(d.realised.bias)} MW`} />}
      </div>

      <div className="card">
        <h2>Forecast known at decision time</h2>
        <p className="desc">
          For each half-hour, the latest forecast published before {d.cutoff_local} UK time on the day before delivery.
          {delivered ? " Actuals are overlaid because this day has already been delivered." : ""}
        </p>
        <Legend items={[
          { label: "Forecast", color: "var(--series-1)" },
          ...(hasBand ? [{ label: "80% interval from last 7 days' errors", color: "var(--band)", box: true }] : []),
          ...(delivered ? [{ label: "Actual", color: "var(--series-2)" }] : []),
        ]} />
        <ResponsiveContainer width="100%" height={340}>
          <ComposedChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="t" tickFormatter={fmtTime} interval={7} {...AXIS} tickLine={false} axisLine={{ stroke: "var(--axis)" }} />
            <YAxis tickFormatter={(v) => `${v / 1000}`} {...AXIS} tickLine={false} axisLine={false} width={44}
              label={{ value: "GW", angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 12 }} />
            <Tooltip content={<Tip
              title={(p) => `${fmtDay(p.t)} ${fmtTime(p.t)} (UK)`}
              build={(p) => [
                { label: "Forecast", value: mw(p.forecast) },
                ...(p.lower != null ? [{ label: "80% range", value: `${num(p.lower)} – ${num(p.upper)} MW` }] : []),
                ...(p.actual != null ? [{ label: "Actual", value: mw(p.actual) }] : []),
                { label: "Forecast made", value: fmtDateTime(p.publish) },
              ]} />} />
            {hasBand && <Area dataKey="bandBase" stackId="b" stroke="none" fill="transparent" isAnimationActive={false} connectNulls />}
            {hasBand && <Area dataKey="bandSize" stackId="b" stroke="none" fill="var(--band)" isAnimationActive={false} connectNulls />}
            <Line dataKey="forecast" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
            {delivered && <Line dataKey="actual" stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />}
          </ComposedChart>
        </ResponsiveContainer>
        <TableView
          columns={[
            { key: "t", label: "Time (UK)", fmt: (v) => fmtTime(v) },
            { key: "forecast", label: "Forecast MW", fmt: num },
            { key: "lower", label: "Low MW", fmt: num },
            { key: "upper", label: "High MW", fmt: num },
            { key: "actual", label: "Actual MW", fmt: num },
          ]}
          rows={d.series}
        />
        <p className="note">
          The interval is the 10th–90th percentile of (forecast − actual) over the previous 7 delivery days at the same
          cutoff; only days up to D-2 are used, so it contains nothing unknown at decision time.
        </p>
      </div>
    </>
  );
}
