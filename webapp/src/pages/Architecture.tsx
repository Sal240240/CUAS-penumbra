import { ILLUMINATORS } from "../physics/illuminators";

const LAYERS = [
  { name: "Sensing", detail: "Receive-only front end per band; ambient EM observations at each node" },
  { name: "Timing", detail: "GNSS-disciplined OCXO + PTP fallback; sub-100 ns inter-node sync" },
  { name: "Edge processing", detail: "Direct-signal cancellation (ECA), cross-ambiguity function, CFAR" },
  { name: "Network", detail: "Compressed range-Doppler features over the mesh backhaul" },
  { name: "Environmental model", detail: "Adaptive baseline of normal multistatic propagation state" },
  { name: "Inference", detail: "Physics-conditioned detector: occupancy heat-map + calibrated uncertainty" },
  { name: "Fusion", detail: "Multistatic UKF refines confirmed tracks against raw range/Doppler" },
  { name: "C2 gateway", detail: "Internal track schema → CoT / SAPIENT adapters" },
];

const BANDS = Object.values(ILLUMINATORS).filter((i) => i.kind !== "leo");

export function Architecture() {
  return (
    <>
      <section className="section" style={{ paddingTop: 48 }}>
        <div className="container">
          <div className="eyebrow">Architecture</div>
          <h1>Coherent passive multistatic radar, not "listening for drones."</h1>
          <p style={{ maxWidth: 720 }}>
            PENUMBRA is a passive coherent location (PCL) system: every node runs a reference
            channel (a clean copy of an illuminator's signal) alongside one or more surveillance
            channels (the same illuminator's signal after reflecting off the environment and any
            targets in it). Cross-correlating the two channels over an integration time recovers
            bistatic range and Doppler with a coherent processing gain of <code>B·T_int</code> —
            for a 6 MHz ATSC channel over 0.5 s that is +65 dB, the entire difference between
            "maybe" and "detects a 249 g drone at 1.2 km." See it computed live in the{" "}
            <a href="/simulator">link-budget simulator</a>.
          </p>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="eyebrow">Pipeline</div>
          <h2>Eight layers, one internal track schema.</h2>
          <div className="pipeline">
            {LAYERS.map((l, i) => (
              <div className="pipeline-step" key={l.name}>
                <div className="pipeline-index">{String(i + 1).padStart(2, "0")}</div>
                <div>
                  <h3 style={{ margin: "0 0 4px" }}>{l.name}</h3>
                  <p style={{ margin: 0, fontSize: "0.9rem" }}>{l.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="eyebrow">Illuminators of opportunity</div>
          <h2>Three concurrent bands, three different jobs.</h2>
          <p style={{ maxWidth: 720 }}>
            One radio family (the AD9361/AD9363-class transceiver already used across the node
            design) tunes 70 MHz–6 GHz, so adding a band is an antenna and firmware decision, not
            a new receiver. Every entry below is a real, published illuminator — see the source
            note on each and the full physics behind it in <a href="/simulator">the simulator</a>.
          </p>
          <div className="grid grid-3" style={{ marginTop: 20 }}>
            {BANDS.map((b) => (
              <div className="panel" key={b.key}>
                <div className="tag accent">{b.kind.toUpperCase()}</div>
                <h3 style={{ margin: "10px 0 6px" }}>{b.name}</h3>
                <p className="mono" style={{ fontSize: "0.82rem", color: "var(--text-faint)", margin: "0 0 10px" }}>
                  {(b.freqHz / 1e6).toFixed(1)} MHz · {(b.bandwidthHz / 1e6).toFixed(1)} MHz BW · {b.eirpDbw.toFixed(1)} dBW EIRP
                </p>
                <p style={{ fontSize: "0.86rem", marginBottom: 8 }}>{b.strengths[0]}</p>
                <p style={{ fontSize: "0.78rem", color: "var(--text-faint)", margin: 0 }}>{b.source}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section" style={{ borderBottom: "none" }}>
        <div className="container grid grid-2">
          <div className="panel">
            <h3 style={{ marginTop: 0 }}>Direct-signal interference is the real limiter</h3>
            <p>
              The direct path from a UHF broadcast tower to a rooftop node is enormously stronger
              than any target echo. Extensive cancellation (ECA, ~50 dB) plus the sidelobe floor of
              a noise-like reference (another <code>B·T_int</code> term) is what makes the weak echo
              recoverable at all — this is exactly what the DSI floor in the link-budget model
              represents, and why the simulator reports whichever of the thermal-noise floor or the
              DSI floor is worse.
            </p>
          </div>
          <div className="panel">
            <h3 style={{ marginTop: 0 }}>Rotor micro-Doppler is the classifier, not a bonus</h3>
            <p>
              A spinning rotor blade produces a periodic "flash" in the Doppler spectrum at
              <code> N·RPM/60</code> Hz (the HERM line spacing) that a bird's wingbeat or a car's
              wheels do not. At UHF a 30 cm airframe sits in the resonance region for a strong body
              return, but electrically small blades barely register; at 3.5 GHz and on the mesh's
              own 5–6 GHz Wi-Fi links, blades are large relative to the wavelength and produce rich,
              classifiable micro-Doppler. Splitting the bands by job (area detection vs. precision
              Doppler vs. street-canyon fill) is why PENUMBRA runs three bands at once.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
