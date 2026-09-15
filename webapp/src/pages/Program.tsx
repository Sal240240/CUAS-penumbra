const GATES = [
  { gate: "1 — Physics", pass: "A measurable, repeatable multistatic echo exists on a Mini-class drone under controlled conditions." },
  { gate: "2 — Repeatability", pass: "The effect is repeatable across runs and receiver sets; false-alarm baseline characterized." },
  { gate: "3 — Urban robustness", pass: "Effect remains useful amid realistic background variability, occlusion, and multipath." },
  { gate: "4 — Localization", pass: "The system infers meaningful multistatic position and velocity, not just a binary alarm." },
  { gate: "5 — Operational performance", pass: "Detection and tracking meet predefined thresholds across the full test-scenario matrix." },
  { gate: "6 — Integration", pass: "Track data is consumed correctly by a representative downstream C2 system." },
];

const SCHEDULE = [
  { month: "1", objective: "Requirements + state of the art", evidence: "SRS; CONOPS; prior-art map" },
  { month: "2", objective: "Physics model + experimental design", evidence: "Measurement hypotheses; test protocols" },
  { month: "3", objective: "Sensor prototype", evidence: "Node V0.1" },
  { month: "4", objective: "Initial data collection", evidence: "Controlled dataset" },
  { month: "5", objective: "Distributed network", evidence: "Multi-node prototype" },
  { month: "6", objective: "Environmental baseline", evidence: "Baseline + false-alarm characterization" },
  { month: "7", objective: "Urban testing", evidence: "Urban dataset" },
  { month: "8", objective: "Detection algorithms", evidence: "Benchmark results" },
  { month: "9", objective: "Tracking", evidence: "Track engine + uncertainty" },
  { month: "10", objective: "C2 integration", evidence: "Gateway prototype" },
  { month: "11", objective: "Stress testing", evidence: "Resilience + failure analysis" },
  { month: "12", objective: "Final demonstration", evidence: "Evidence package + final report" },
];

const RISKS = [
  { risk: "Coherent echo too weak at UHF range", likelihood: "Medium", impact: "High", mitigation: "Gate 1 physics validation before scale-up; LTE/5G bands provide a shorter-baseline fallback" },
  { risk: "Urban multipath overwhelms the target return", likelihood: "High", impact: "High", mitigation: "Adaptive baseline; per-cell diffraction modelling; geometry optimization via coverage simulation" },
  { risk: "False-alarm rate too high in dense RF environments", likelihood: "Medium", impact: "High", mitigation: "Long-duration background collection; multistatic residual consistency check; evidence-ledger corroboration" },
  { risk: "Node synchronization insufficient for Doppler tracking", likelihood: "Medium", impact: "High", mitigation: "GNSS-disciplined OCXO with PTP fallback; explicit timing error budget" },
  { risk: "GNSS denial at a CUAS demonstration", likelihood: "Medium", impact: "Medium", mitigation: "OCXO holdover (~1e-9/day); PTP over backhaul; reference-channel self-calibration" },
  { risk: "Technology overlap with prior ambient-EM sensing concepts", likelihood: "Medium", impact: "Medium", mitigation: "Differentiation is architectural and evidential (mesh + multi-band + evidence ledger), not the word \"passive\" — see the honest novelty statement below" },
  { risk: "Sim-to-real gap in the ML detector", likelihood: "High", impact: "Medium", mitigation: "Physics-based simulator as primary training source; pretrained on public measured micro-Doppler sets; Gate 3 requires retraining on real WP6 data" },
];

export function Program() {
  return (
    <>
      <section className="section" style={{ paddingTop: 48 }}>
        <div className="container">
          <div className="eyebrow">Program</div>
          <h1>Physics-first, gated, and honest about negative results.</h1>
          <p style={{ maxWidth: 720 }}>
            The program deliberately starts with physics validation and falsification, not
            AI-first development. Every major phase has a documented gate; a negative result at
            Gate 1 stops the program and publishes why, rather than quietly pivoting the marketing.
          </p>
          <div className="callout ok" style={{ marginTop: 20, maxWidth: 720 }}>
            <p>
              <strong>Honest novelty statement:</strong> "PENUMBRA introduces a differentiated
              sensing architecture based on distributed urban multistatic propagation inference.
              Related passive and ambient electromagnetic sensing concepts exist; the proposed
              contribution is the integrated use of coherent multi-band passive coherent location,
              a mesh network that is also its own Wi-Fi illuminator, an evidence ledger that audits
              every classification, and C2-ready track generation as a single CUAS detection
              architecture." Any IP or "first ever" claim is preceded by a formal literature and
              patent review (WP2).
            </p>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="eyebrow">Stage gates</div>
          <h2>Six gates from "does the physics exist" to "can C2 consume it."</h2>
          <table>
            <thead><tr><th>Gate</th><th>Pass condition</th></tr></thead>
            <tbody>
              {GATES.map((g) => (
                <tr key={g.gate}><td style={{ whiteSpace: "nowrap" }}><strong>{g.gate}</strong></td><td>{g.pass}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="eyebrow">12-month schedule</div>
          <h2>One objective and one piece of evidence per month.</h2>
          <table>
            <thead><tr><th>Month</th><th>Objective</th><th>Expected evidence</th></tr></thead>
            <tbody>
              {SCHEDULE.map((s) => (
                <tr key={s.month}><td className="mono">{s.month}</td><td>{s.objective}</td><td>{s.evidence}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section" style={{ borderBottom: "none" }}>
        <div className="container">
          <div className="eyebrow">Risk register</div>
          <h2>What could kill this program, and what we're doing about it now.</h2>
          <table>
            <thead><tr><th>Risk</th><th>Likelihood</th><th>Impact</th><th>Mitigation</th></tr></thead>
            <tbody>
              {RISKS.map((r) => (
                <tr key={r.risk}>
                  <td>{r.risk}</td>
                  <td><span className={`tag ${r.likelihood === "High" ? "warn" : ""}`}>{r.likelihood}</span></td>
                  <td><span className={`tag ${r.impact === "High" ? "warn" : ""}`}>{r.impact}</span></td>
                  <td style={{ fontSize: "0.86rem" }}>{r.mitigation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
