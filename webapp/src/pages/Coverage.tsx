import { useMemo, useState } from "react";
import { demoDowntownScene } from "../physics/scene";
import { coverageMap } from "../physics/coverage";
import { TARGETS } from "../physics/rcs";

const TARGET_KEYS = Object.keys(TARGETS).filter((k) => TARGETS[k].classLabel !== "vehicle");

export function Coverage() {
  const [targetKey, setTargetKey] = useState("dji_mavic");
  const [minPairs, setMinPairs] = useState(3);
  const scene = useMemo(() => demoDowntownScene(), []);
  const result = useMemo(
    () => coverageMap(scene, { targetKey, stepM: 30, minPairs }),
    [scene, targetKey, minPairs],
  );

  const w = 640;
  const h = 640;
  const e = scene.extentM;
  const sx = (x: number) => ((x + e) / (2 * e)) * w;
  const sy = (y: number) => h - ((y + e) / (2 * e)) * h;
  const cell = (w / result.x.length) * 1.02;

  const coveredCount = result.covered.flat().filter(Boolean).length;
  const totalCells = result.covered.flat().length;

  return (
    <section className="section" style={{ paddingTop: 48, borderBottom: "none" }}>
      <div className="container">
        <div className="eyebrow">Interactive · stylised Ottawa-core scene</div>
        <h1>Mesh coverage map</h1>
        <p style={{ maxWidth: 720 }}>
          Six rooftop nodes against a stylised downtown grid (block sizes and heights matching the
          Ottawa core in character, not a survey — see <code>penumbra/sim/scene.py</code>). For
          every point at 40 m altitude, this evaluates the full link budget — including knife-edge
          diffraction over intervening rooftops (ITU-R P.526-15, Deygout method) — for every
          illuminator/node pair, and counts how many pairs clear the detection threshold.{" "}
          <span className="mono" style={{ color: "var(--accent)" }}>≥3 pairs</span> gives a
          bistatic-range position fix; fewer means the point is seen but not yet localisable.
        </p>

        <div className="grid" style={{ gridTemplateColumns: "260px 1fr", marginTop: 24, alignItems: "start" }}>
          <div className="panel">
            <h3 style={{ marginTop: 0 }}>Scenario</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <label>Target</label>
                <select value={targetKey} onChange={(e2) => setTargetKey(e2.target.value)}>
                  {TARGET_KEYS.map((k) => <option key={k} value={k}>{TARGETS[k].name}</option>)}
                </select>
              </div>
              <div>
                <label>Minimum pairs for a position fix: {minPairs}</label>
                <input type="range" min={1} max={5} step={1} value={minPairs} onChange={(e2) => setMinPairs(Number(e2.target.value))} />
              </div>
              <div className="stat">
                <div className="value">{((coveredCount / totalCells) * 100).toFixed(0)}%</div>
                <div className="label">Area with a position fix</div>
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-faint)" }}>
                <p style={{ marginBottom: 6 }}><strong>Nodes ({scene.nodes.length}):</strong> rooftop, 30–55 m AGL, ~330 m ring radius.</p>
                <p style={{ marginBottom: 0 }}><strong>Illuminators:</strong> ATSC ch.25/32 (Camp Fortune, ~15.7 km), 3× LTE 700 MHz sectors, 2× 5G n78 sectors — all outside this frame, bearings noted below.</p>
              </div>
            </div>
          </div>

          <div className="panel" style={{ padding: 8 }}>
            <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Coverage heat-map of the downtown scene">
              <rect x={0} y={0} width={w} height={h} fill="var(--bg)" />
              {result.x.map((x, ix) =>
                result.y.map((y, iy) => {
                  const n = result.nPairs[iy][ix];
                  if (n === 0) return null;
                  const covered = result.covered[iy][ix];
                  const alpha = Math.min(0.15 + n * 0.13, 0.9);
                  return (
                    <rect
                      key={`${ix}-${iy}`}
                      x={sx(x) - cell / 2} y={sy(y) - cell / 2} width={cell} height={cell}
                      fill={covered ? `rgba(94,234,212,${alpha})` : `rgba(245,166,35,${alpha * 0.7})`}
                    />
                  );
                }),
              )}
              {scene.buildings.map((b, i) => (
                <rect
                  key={i} x={sx(b.x0)} y={sy(b.y1)} width={sx(b.x1) - sx(b.x0)} height={sy(b.y0) - sy(b.y1)}
                  fill="rgba(159,176,184,0.14)" stroke="rgba(159,176,184,0.28)" strokeWidth={1}
                />
              ))}
              {scene.nodes.map((n) => (
                <g key={n.nodeId}>
                  <circle cx={sx(n.pos[0])} cy={sy(n.pos[1])} r={6} fill="var(--bg)" stroke="var(--accent)" strokeWidth={2} />
                  <text x={sx(n.pos[0]) + 9} y={sy(n.pos[1]) + 4} fontSize={11} fill="var(--text)" fontFamily="var(--font-mono)">{n.nodeId}</text>
                </g>
              ))}
            </svg>
            <div style={{ display: "flex", gap: 16, fontSize: "0.78rem", color: "var(--text-faint)", padding: "8px 8px 2px" }}>
              <LegendSwatch color="rgba(94,234,212,0.7)" label={`≥ ${minPairs} pairs (position fix)`} />
              <LegendSwatch color="rgba(245,166,35,0.5)" label="1–2 pairs (seen, not localisable)" />
              <LegendSwatch color="rgba(159,176,184,0.2)" label="Building footprint" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 10, height: 10, borderRadius: 2, background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}
