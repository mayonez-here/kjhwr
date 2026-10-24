import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";
import { mw, num, pct, signed } from "./format";
import { Status, TableView, Tip, useAsync } from "./ui";

const AXIS = { stroke: "var(--muted)", fontSize: 12 };

export default function Horizon({ start, end }) {
  const state = useAsync(() => api.horizon(start, end), [start, end]);
  return (
    <Status state={state}>
      {(h) => {
        const rows = h.by_horizon;
        if (!rows.length) return <div className="banner warn">No data for this range.</div>;
        return (
          <div className="card">
            <h2>Error vs forecast lead time</h2>
            <p className="desc">
              Every published forecast run, grouped by how far ahead of delivery it was made. Shows how much more you can
              trust a forecast as delivery approaches – and what waiting for a fresher run would buy.
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--grid)" vertical={false} />
                <XAxis dataKey="bucket" {...AXIS} tickLine={false} axisLine={{ stroke: "var(--axis)" }} />
                <YAxis {...AXIS} tickLine={false} axisLine={false} width={48}
                  label={{ value: "MAE, MW", angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 12 }} />
                <Tooltip cursor={{ fill: "var(--grid)", opacity: 0.5 }} content={<Tip
                  title={(p) => `Made ${p.bucket} before delivery`}
                  build={(p) => [
                    { label: "MAE", value: mw(p.mae) }, { label: "RMSE", value: mw(p.rmse) },
                    { label: "Bias", value: `${signed(p.bias)} MW` }, { label: "Samples", value: num(p.n) },
                  ]} />} />
                <Bar dataKey="mae" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
            <TableView summary="Show as table" columns={[
              { key: "bucket", label: "Lead time" }, { key: "n", label: "Samples", fmt: num },
              { key: "mae", label: "MAE", fmt: num }, { key: "rmse", label: "RMSE", fmt: num },
              { key: "bias", label: "Bias", fmt: signed }, { key: "wape_pct", label: "WAPE", fmt: pct },
            ]} rows={rows} />
          </div>
        );
      }}
    </Status>
  );
}
