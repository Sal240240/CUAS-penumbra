import { useMemo, useState } from "react";
import { buildLedger, combine, type Observation } from "../physics/evidence";

const PRESETS: Record<string, Observation> = {
  confident_drone: {
    flashHz: 216, tipDopplerHz: 1700, bandFreqHz: 3.5e9, nPairs: 5, nBands: 3,
    nisSigma: 1.2, hoverS: 4.5, maxSpeedMps: 18, maxAccelMps2: 3, altAglM: 61, altSigmaM: 8,
    onStreetAxis: false, persistenceS: 6.0,
  },
  gull: {
    flashHz: 4.2, nPairs: 4, nBands: 2, nisSigma: 1.5, hoverS: 0, maxSpeedMps: 12, maxAccelMps2: 1.5,
    altAglM: 45, altSigmaM: 12, onStreetAxis: false, persistenceS: 8.0, wingbeatHz: 4.2,
  },
  car: {
    nPairs: 2, nBands: 1, hoverS: 0, maxSpeedMps: 14, maxAccelMps2: 2, altAglM: 1.0, altSigmaM: 2.0,
    onStreetAxis: true, persistenceS: 5.0,
  },
  ambiguous_ghost: {
    nPairs: 2, nBands: 1, nisSigma: 3.4, hoverS: 0, maxSpeedMps: 6, maxAccelMps2: 1, onStreetAxis: false,
    persistenceS: 1.2,
  },
};

const PRESET_LABELS: Record<string, string> = {
  confident_drone: "Confident drone — hovering Mavic-class",
  gull: "Gull — wingbeat, no hover",
  car: "Passenger car — street-constrained",
  ambiguous_ghost: "Weak / ambiguous — 2 pairs, high residual",
};

export function Evidence() {
  const [presetKey, setPresetKey] = useState("confident_drone");
  const obs = PRESETS[presetKey];
  const ledger = useMemo(() => buildLedger(obs), [obs]);
  const probs = useMemo(() => combine(ledger), [ledger]);
  const topClass = (Object.entries(probs) as [string, number][]).sort((a, b) => b[1] - a[1])[0][0];

  return (
    <>
      <section className="section" style={{ paddingTop: 48 }}>
        <div className="container">
          <div className="eyebrow">Interactive</div>
          <h1>Every track is explained, not just scored.</h1>
          <p style={{ maxWidth: 720 }}>
            A neural fusion score is not something a radar engineer, a test director, or a court
            can audit. The evidence ledger re-derives each classification from named physical
            evidence across three axes — <strong>real</strong> (object vs. ghost intersection),{" "}
            <strong>airborne</strong> (vs. ground vehicle), and <strong>drone</strong> (vs. bird) —
            each with an explicit log-odds contribution, then combines them as a product of
            experts. The network's own confidence is capped so unaudited evidence can never
            outweigh an explained physical case.
          </p>
        </div>
      </section>

      <section className="section" style={{ borderBottom: "none" }}>
        <div className="container">
          <div style={{ marginBottom: 20 }}>
            <label>Scenario</label>
            <select value={presetKey} onChange={(e) => setPresetKey(e.target.value)} style={{ maxWidth: 420 }}>
              {Object.keys(PRESETS).map((k) => <option key={k} value={k}>{PRESET_LABELS[k]}</option>)}
            </select>
          </div>

          <div className="grid grid-2" style={{ alignItems: "start" }}>
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>Evidence ledger</h3>
              <ul className="citation-list">
                {ledger.map((e, i) => (
                  <li key={i}>
                    <span className="tag" style={{ marginRight: 8 }}>{e.axis}</span>
                    <span className="mono" style={{ color: e.logOdds >= 0 ? "var(--ok)" : "var(--danger)" }}>
                      {e.logOdds >= 0 ? "+" : ""}{(e.logOdds * e.weight).toFixed(1)}
                    </span>{" "}
                    {e.statement}
                  </li>
                ))}
                {ledger.length === 0 && <li>No qualifying evidence for this scenario.</li>}
              </ul>
            </div>
            <div className="panel">
              <h3 style={{ marginTop: 0 }}>Combined classification</h3>
              {(Object.entries(probs) as [string, number][])
                .sort((a, b) => b[1] - a[1])
                .map(([cls, p]) => (
                  <div key={cls} style={{ marginBottom: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: 4 }}>
                      <span style={{ textTransform: "capitalize", color: cls === topClass ? "var(--text)" : "var(--text-faint)" }}>{cls}</span>
                      <span className="mono">{(p * 100).toFixed(1)}%</span>
                    </div>
                    <div style={{ height: 8, background: "var(--bg-raised)", borderRadius: 4, overflow: "hidden" }}>
                      <div style={{ width: `${p * 100}%`, height: "100%", background: cls === topClass ? "var(--accent)" : "var(--border-strong)" }} />
                    </div>
                  </div>
                ))}
              <p style={{ fontSize: "0.8rem", color: "var(--text-faint)", marginTop: 16, marginBottom: 0 }}>
                This published classification is exactly the sequence of statements above — nothing
                is asserted that the ledger does not justify.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="section" style={{ borderBottom: "none" }}>
        <div className="container">
          <div className="eyebrow">C2 interoperability</div>
          <h2>Confirmed tracks translate to standard C2 schemas.</h2>
          <p style={{ maxWidth: 720 }}>
            The internal track schema (<code>penumbra/tracking/schema.py</code>) is stable and
            carries full uncertainty and evidence provenance; adapters translate it outward without
            re-deriving anything. A Cursor-on-Target adapter (<code>penumbra/c2/cot.py</code>) is
            implemented now; SAPIENT-style messages (<code>penumbra/c2/sapient.py</code>) and
            JREAP-C/VMF are evaluated per the applicable test environment rather than assumed.
          </p>
          <div className="panel mono" style={{ fontSize: "0.78rem", overflowX: "auto", whiteSpace: "pre" }}>
{`<event version="2.0" uid="PENUMBRA-FABRIC-01.T0042" type="a-u-A-M-H-Q" how="m-p" ...>
  <point lat="45.4231000" lon="-75.6980000" hae="121.4" ce="6.2" le="4.1"/>
  <detail>
    <track speed="18.20" course="214.6"/>
    <contact callsign="PNMB-T0042"/>
    <remarks>drone p=0.92 conf=0.88 status=confirmed pairs=5</remarks>
    <__penumbra status="confirmed" confidence="0.880" quality="0.910" n_pairs="5">
      <class name="drone" p="0.919"/>
      <evidence kind="micro_doppler" log_odds="+2.80">HERM line spacing 216 Hz consistent with a rotor...</evidence>
    </__penumbra>
  </detail>
</event>`}
          </div>
        </div>
      </section>
    </>
  );
}
