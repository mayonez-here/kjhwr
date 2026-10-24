import { useEffect, useState } from "react";
import { api } from "./api";
import Accuracy from "./Accuracy.jsx";
import Decision from "./Decision.jsx";
import Horizon from "./Horizon.jsx";
import { fmtDay } from "./format";
import { Status, useAsync } from "./ui";

const TABS = [
  { id: "decision", label: "Decision view" },
  { id: "accuracy", label: "Forecast accuracy" },
  { id: "horizon", label: "Lead-time analysis" },
];

export default function App() {
  const state = useAsync(() => api.meta(), []);
  return (
    <div className="wrap">
      <header className="top">
        <h1>Wind Forecast Desk</h1>
        <span className="sub">GB day-ahead buying · national wind · Elexon FUELHH / WINDFOR</span>
        <span className="spacer" />
        <ThemeToggle />
      </header>
      <Status state={state}>{(meta) => <Main meta={meta} />}</Status>
    </div>
  );
}

function Main({ meta }) {
  const days = meta.delivery_days;
  const [tab, setTab] = useState("decision");
  const [day, setDay] = useState(days[Math.min(13, days.length - 1)]); // default: mid-month so a band exists
  const [cutoff, setCutoff] = useState(meta.default_cutoff);
  const [start, setStart] = useState(days[0]);
  const [end, setEnd] = useState(days[days.length - 2]); // 31 Jan: last day with decisions made in January

  return (
    <>
      {meta.synthetic && (
        <div className="banner warn">
          <b>Synthetic demo data.</b> This build is not showing real Elexon data. Run <code>python scripts/fetch_data.py</code> to load January 2026.
        </div>
      )}

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </nav>

      <div className="controls">
        {tab === "decision" && (
          <label>Delivery day
            <select value={day} onChange={(e) => setDay(e.target.value)}>
              {days.map((d) => <option key={d} value={d}>{fmtDay(d)} (decide {fmtDay(new Date(Date.parse(d) - 864e5))})</option>)}
            </select>
          </label>
        )}
        {tab !== "decision" && (
          <>
            <label>From
              <select value={start} onChange={(e) => setStart(e.target.value)}>
                {days.filter((d) => d <= end).map((d) => <option key={d} value={d}>{fmtDay(d)}</option>)}
              </select>
            </label>
            <label>To
              <select value={end} onChange={(e) => setEnd(e.target.value)}>
                {days.filter((d) => d >= start).map((d) => <option key={d} value={d}>{fmtDay(d)}</option>)}
              </select>
            </label>
          </>
        )}
        {tab !== "horizon" && (
          <label>Gate closure (UK time, day before)
            <input type="time" value={cutoff} onChange={(e) => e.target.value && setCutoff(e.target.value)} />
          </label>
        )}
      </div>

      {tab === "decision" && <Decision meta={meta} day={day} cutoff={cutoff} />}
      {tab === "accuracy" && <Accuracy start={start} end={end} cutoff={cutoff} />}
      {tab === "horizon" && <Horizon start={start} end={end} />}

      <p className="note" style={{ marginTop: 24 }}>
        Data: Elexon Insights Solution (BMRS), snapshot {meta.fetched_at?.slice(0, 10) ?? "n/a"} ·{" "}
        {meta.counts.actual_points.toLocaleString("en-GB")} actual points, {meta.counts.forecast_rows.toLocaleString("en-GB")} forecast rows.
        Gate closure is an assumption (default {meta.default_cutoff}); change it above.
      </p>
    </>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("theme") || "auto"; } catch { return "auto"; }
  });
  useEffect(() => {
    const el = document.documentElement;
    if (theme === "auto") el.removeAttribute("data-theme"); else el.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch { /* storage unavailable */ }
  }, [theme]);
  return (
    <select aria-label="Theme" value={theme} onChange={(e) => setTheme(e.target.value)}>
      <option value="auto">Theme: auto</option>
      <option value="light">Light</option>
      <option value="dark">Dark</option>
    </select>
  );
}
