import { useMemo, useState } from "react";
import { linkBudget, maxDetectionRangeM, geomspace } from "../physics/bistatic";
import { bodyRcs, TARGETS } from "../physics/rcs";
import { ILLUMINATORS } from "../physics/illuminators";

const ILLUM_KEYS = Object.keys(ILLUMINATORS);
const TARGET_KEYS = Object.keys(TARGETS);

export function Simulator() {
  const [illumKey, setIllumKey] = useState("cbot_dt");
  const [targetKey, setTargetKey] = useState("dji_mavic");
  const [rT, setRT] = useState(15700);
  const [rR, setRR] = useState(400);
  const [baseline, setBaseline] = useState(15900);
  const [tInt, setTInt] = useState(0.5);
  const [extraLoss, setExtraLoss] = useState(0);
  const [threshold, setThreshold] = useState(13);

  const illum = ILLUMINATORS[illumKey];
  const target = TARGETS[targetKey];

  const result = useMemo(() => {
    return linkBudget({
      eirpDbw: illum.eirpDbw, freqHz: illum.freqHz, bandwidthHz: illum.bandwidthHz,
      tIntS: tInt * illum.dutyCycle, sigmaDbsm: bodyRcs(target, illum.freqHz),
      rTM: rT, rRM: rR, baselineM: baseline, extraPathLossDb: extraLoss,
      detectionThresholdDb: threshold,
    });
  }, [illum, target, rT, rR, baseline, tInt, extraLoss, threshold]);

  const maxRange = useMemo(() => {
    return maxDetectionRangeM({
      eirpDbw: illum.eirpDbw, freqHz: illum.freqHz, bandwidthHz: illum.bandwidthHz,
      tIntS: tInt * illum.dutyCycle, sigmaDbsm: bodyRcs(target, illum.freqHz),
      rTM: rT, baselineM: baseline, extraPathLossDb: extraLoss, detectionThresholdDb: threshold,
    });
  }, [illum, target, rT, baseline, tInt, extraLoss, threshold]);

  const curve = useMemo(() => {
    const grid = geomspace(20, 5000, 120);
    return grid.map((r) => {
      const lb = linkBudget({
        eirpDbw: illum.eirpDbw, freqHz: illum.freqHz, bandwidthHz: illum.bandwidthHz,
        tIntS: tInt * illum.dutyCycle, sigmaDbsm: bodyRcs(target, illum.freqHz),
        rTM: rT, rRM: r, baselineM: baseline, extraPathLossDb: extraLoss, detectionThresholdDb: threshold,
      });
      return { r, snr: lb.snrDb };
    });
  }, [illum, target, rT, baseline, tInt, extraLoss, threshold]);

  return (
    <section className="section" style={{ paddingTop: 48, borderBottom: "none" }}>
      <div className="container">
        <div className="eyebrow">Interactive · runs entirely in your browser</div>
        <h1>Link-budget simulator</h1>
        <p style={{ maxWidth: 720 }}>
          This computes the exact bistatic radar equation and detectability floors used in the
          Python physics core (<code>penumbra/physics/bistatic.py</code>) — the TypeScript port is
          checked for bit-for-bit numerical agreement against it. Change the geometry, illuminator,
          or target below and watch the SNR floors move.
        </p>

        <div className="grid grid-2" style={{ marginTop: 28, alignItems: "start" }}>
          <div className="panel">
            <h3 style={{ marginTop: 0 }}>Scenario</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <label>Illuminator</label>
                <select value={illumKey} onChange={(e) => setIllumKey(e.target.value)}>
                  {ILLUM_KEYS.map((k) => <option key={k} value={k}>{ILLUMINATORS[k].name}</option>)}
                </select>
              </div>
              <div>
                <label>Target</label>
                <select value={targetKey} onChange={(e) => setTargetKey(e.target.value)}>
                  {TARGET_KEYS.map((k) => <option key={k} value={k}>{TARGETS[k].name}</option>)}
                </select>
              </div>
              <SliderField label={`Illuminator → target range: ${fmt(rT)} m`} min={50} max={20000} step={10} value={rT} onChange={setRT} log />
              <SliderField label={`Node → target range: ${fmt(rR)} m`} min={20} max={5000} step={10} value={rR} onChange={setRR} log />
              <SliderField label={`Illuminator → node baseline: ${fmt(baseline)} m`} min={50} max={20000} step={10} value={baseline} onChange={setBaseline} log />
              <SliderField label={`Integration time: ${tInt.toFixed(2)} s`} min={0.05} max={2.0} step={0.05} value={tInt} onChange={setTInt} />
              <SliderField label={`Extra path loss (diffraction/foliage): ${extraLoss.toFixed(0)} dB`} min={0} max={45} step={1} value={extraLoss} onChange={setExtraLoss} />
              <SliderField label={`Detection threshold: ${threshold.toFixed(0)} dB`} min={8} max={20} step={0.5} value={threshold} onChange={setThreshold} />
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div className={`panel ${result.detectable ? "" : ""}`}>
              <div className="grid grid-2">
                <div className={`stat ${result.detectable ? "ok" : "danger"}`}>
                  <div className="value">{result.snrDb.toFixed(1)} dB</div>
                  <div className="label">Usable SNR</div>
                </div>
                <div className="stat">
                  <div className="value">{result.detectable ? "DETECT" : "NO DETECT"}</div>
                  <div className="label">vs. {threshold.toFixed(0)} dB threshold</div>
                </div>
                <div className="stat">
                  <div className="value">{result.snrThermalDb.toFixed(1)} dB</div>
                  <div className="label">Thermal-noise floor</div>
                </div>
                <div className="stat">
                  <div className="value">{result.snrDsiDb.toFixed(1)} dB</div>
                  <div className="label">Direct-signal-interference floor</div>
                </div>
                <div className="stat">
                  <div className="value">{result.rangeResolutionM.toFixed(1)} m</div>
                  <div className="label">Range resolution (c/B)</div>
                </div>
                <div className="stat">
                  <div className="value">{result.dopplerResolutionHz.toFixed(2)} Hz</div>
                  <div className="label">Doppler resolution (1/T)</div>
                </div>
              </div>
              <p style={{ fontSize: "0.82rem", marginTop: 16, marginBottom: 0, color: "var(--text-faint)" }}>
                The usable SNR is the <em>smaller</em> of the two floors — whichever one is worse
                sets what you'd actually see. At long UHF baselines the DSI floor usually wins; at
                short mesh Wi-Fi baselines with heavy cancellation, thermal noise usually wins.
              </p>
            </div>

            <div className="panel">
              <h3 style={{ marginTop: 0, marginBottom: 4 }}>Detection range at fixed illuminator distance</h3>
              <p style={{ fontSize: "0.85rem", marginTop: 0 }}>
                Maximum node-to-target range that still clears the threshold:{" "}
                <strong className="mono">{maxRange > 0 ? `${maxRange.toFixed(0)} m` : "not achievable in this scenario"}</strong>
              </p>
              <SnrCurve curve={curve} thresholdDb={threshold} highlight={rR} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function fmt(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(2)} k` : n.toFixed(0);
}

function SliderField({
  label, min, max, step, value, onChange, log,
}: {
  label: string; min: number; max: number; step: number; value: number;
  onChange: (v: number) => void; log?: boolean;
}) {
  if (!log) {
    return (
      <div>
        <label>{label}</label>
        <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      </div>
    );
  }
  // Logarithmic slider: internal position is log-scaled, exposed value is linear metres.
  const logMin = Math.log(min);
  const logMax = Math.log(max);
  const pos = (Math.log(Math.max(value, min)) - logMin) / (logMax - logMin);
  return (
    <div>
      <label>{label}</label>
      <input
        type="range" min={0} max={1000} step={1} value={Math.round(pos * 1000)}
        onChange={(e) => {
          const p = Number(e.target.value) / 1000;
          onChange(Math.exp(logMin + p * (logMax - logMin)));
        }}
      />
    </div>
  );
}

function SnrCurve({ curve, thresholdDb, highlight }: { curve: { r: number; snr: number }[]; thresholdDb: number; highlight: number }) {
  const w = 560;
  const h = 220;
  const pad = { l: 44, r: 12, t: 12, b: 28 };
  const rs = curve.map((c) => c.r);
  const snrs = curve.map((c) => c.snr);
  const rMin = Math.log(Math.min(...rs));
  const rMax = Math.log(Math.max(...rs));
  const snrMin = Math.min(-10, ...snrs, thresholdDb - 5);
  const snrMax = Math.max(...snrs, thresholdDb + 5);

  const x = (r: number) => pad.l + ((Math.log(r) - rMin) / (rMax - rMin)) * (w - pad.l - pad.r);
  const y = (s: number) => h - pad.b - ((s - snrMin) / (snrMax - snrMin)) * (h - pad.t - pad.b);

  const path = curve.map((c, i) => `${i === 0 ? "M" : "L"}${x(c.r).toFixed(1)},${y(c.snr).toFixed(1)}`).join(" ");
  const thresholdY = y(thresholdDb);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="SNR versus node-to-target range">
      <line x1={pad.l} y1={thresholdY} x2={w - pad.r} y2={thresholdY} stroke="var(--warn)" strokeDasharray="4 4" strokeWidth={1} />
      <text x={w - pad.r} y={thresholdY - 4} textAnchor="end" fontSize={10} fill="var(--warn)" fontFamily="var(--font-mono)">
        {thresholdDb.toFixed(0)} dB threshold
      </text>
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth={2} />
      <line x1={x(highlight)} y1={pad.t} x2={x(highlight)} y2={h - pad.b} stroke="var(--text-faint)" strokeDasharray="2 3" strokeWidth={1} />
      <line x1={pad.l} y1={h - pad.b} x2={w - pad.r} y2={h - pad.b} stroke="var(--border-strong)" />
      <text x={pad.l} y={h - 8} fontSize={10} fill="var(--text-faint)" fontFamily="var(--font-mono)">20 m</text>
      <text x={w - pad.r} y={h - 8} textAnchor="end" fontSize={10} fill="var(--text-faint)" fontFamily="var(--font-mono)">5 km</text>
    </svg>
  );
}
