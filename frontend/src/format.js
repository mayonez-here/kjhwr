const TZ = "Europe/London";

const timeFmt = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false });
const dateTimeFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false,
});
const dayFmt = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "short" });

export const fmtTime = (iso) => timeFmt.format(new Date(iso));
export const fmtDateTime = (iso) => (iso ? dateTimeFmt.format(new Date(iso)) : "–");
export const fmtDay = (iso) => dayFmt.format(new Date(iso));

export const mw = (v) => (v == null ? "–" : `${Math.round(v).toLocaleString("en-GB")} MW`);
export const gw = (v) => (v == null ? "–" : `${(v / 1000).toFixed(1)} GW`);
export const num = (v) => (v == null ? "–" : Math.round(v).toLocaleString("en-GB"));
export const signed = (v) => (v == null ? "–" : `${v > 0 ? "+" : ""}${Math.round(v).toLocaleString("en-GB")}`);
export const pct = (v) => (v == null ? "–" : `${v.toFixed(1)}%`);
