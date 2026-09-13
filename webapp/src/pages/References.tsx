import { IMAGE_CREDITS } from "../data/credits";

const CITATIONS = [
  {
    text: "N. J. Willis, Bistatic Radar, 2nd ed. Raleigh, NC: SciTech Publishing, 2005.",
    note: "Bistatic radar equation (eq. 4.1) underlying penumbra/physics/bistatic.py.",
  },
  {
    text: "H. D. Griffiths and C. J. Baker, An Introduction to Passive Radar. Boston: Artech House, 2017.",
    note: "Thermal and direct-signal-interference detectability floors; the coherent processing-gain argument (B·T_int) the whole link budget rests on.",
  },
  {
    text: "V. C. Chen, The Micro-Doppler Effect in Radar, 2nd ed. Boston: Artech House, 2019.",
    note: "Rotor-blade micro-Doppler model (ch. 3) ported in penumbra/physics/microdoppler.py.",
  },
  {
    text: "ITU-R Recommendation P.526-15, \"Propagation by diffraction,\" International Telecommunication Union, 2019.",
    note: "Single/multiple knife-edge diffraction loss (Deygout method) in penumbra/physics/propagation.py.",
  },
  {
    text: "P. Semkin et al., \"Compact-Range RCS Measurements and Modeling of Small Drones at 15 GHz and 25 GHz,\" arXiv:1911.05926, 2019.",
    note: "Measured DJI Phantom/Mavic RCS anchors in penumbra/physics/rcs.py.",
    url: "https://arxiv.org/abs/1911.05926",
  },
  {
    text: "Á. de Quevedo, F. Urzaiz, J. Menoyo, and A. López, \"Drone detection and radar-cross-section measurements by RAD-DAR,\" IET Radar, Sonar & Navigation, vol. 13, no. 9, pp. 1437–1447, 2019. doi:10.1049/iet-rsn.2018.5646.",
    note: "Phantom-class RCS spread (0.01–0.35 m²) used as a modelling bound.",
    url: "https://doi.org/10.1049/iet-rsn.2018.5646",
  },
  {
    text: "F. Fioranelli, M. Ritchie, H. Borrion, and H. Griffiths, \"Classification of loaded/unloaded micro-drones using multistatic radar,\" Electronics Letters, vol. 51, no. 22, pp. 1813–1815, 2015.",
    note: "Blade-flash-below-body RCS offset used in penumbra/physics/rcs.py.",
    url: "https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/el.2015.3038",
  },
  {
    text: "C. Ji et al., \"Doppler-Based Multistatic Drone Tracking via Cellular Downlink Signals,\" arXiv:2509.25732, 2025.",
    note: "Sub-metre Doppler-only multistatic tracking result motivating the LTE-band mesh geometry.",
    url: "https://arxiv.org/abs/2509.25732",
  },
  {
    text: "P. Jopanya and D. P. M. Osorio, \"Utilizing 5G NR SSB Blocks for Passive Detection and Localization of Low-Altitude Drones,\" in Proc. IEEE 26th Int. Workshop on Signal Processing Advances in Wireless Communications (SPAWC), 2025. arXiv:2504.02641.",
    note: "SSB/PBCH as a deterministic 5G reference signal for passive sensing.",
    url: "https://arxiv.org/abs/2504.02641",
  },
  {
    text: "R. Blázquez-García et al., \"Capabilities and challenges of passive radar systems based on broadband low-Earth orbit communication satellites,\" IET Radar, Sonar & Navigation, 2024. doi:10.1049/rsn2.12446.",
    note: "LEO Ku-band (Starlink) illumination link-budget bound — kept as a Phase E footnote, not a Sandbox claim.",
    url: "https://doi.org/10.1049/rsn2.12446",
  },
  {
    text: "T. E. Humphreys, P. A. Iannucci, Z. M. Komodromos, and A. M. Graff, \"Signal Structure of the Starlink Ku-Band Downlink,\" arXiv:2210.11578, 2022.",
    note: "Starlink frame/synchronization structure used for the same illuminator.",
    url: "https://arxiv.org/abs/2210.11578",
  },
  {
    text: "S. J. Julier and J. K. Uhlmann, \"Unscented filtering and nonlinear estimation,\" Proceedings of the IEEE, vol. 92, no. 3, pp. 401–422, 2004.",
    note: "Unscented Kalman filter used for multistatic range/Doppler refinement.",
  },
  {
    text: "P. Zarchan, Tactical and Strategic Missile Guidance, 7th ed. Reston, VA: AIAA, 2019.",
    note: "Proportional-navigation guidance law (ch. 2–5) in penumbra/sim/intercept.py — a costed roadmap item, not a Sandbox deliverable.",
  },
  {
    text: "Government of Canada, Department of National Defence, \"Counter Uncrewed Aerial Systems Sandbox — Urban Sandbox,\" Defence IDEaS, 2025–2027 applicant guide materials.",
    note: "Program context, non-goals, and the constraint that no defeat mechanism may be demonstrated in the urban sandbox.",
    url: "https://www.canada.ca/en/department-national-defence/programs/defence-ideas/element/sandboxes/challenge/counter-uncrewed-aerial-systems-urban-sandbox-2027.html",
  },
  {
    text: "Innovation, Science and Economic Development Canada, RSS-247: Radio Standards Specification for Digital Transmission Systems, Wireless LAN Devices.",
    note: "Wi-Fi 5 GHz EIRP limits used for the mesh's own illuminator band.",
  },
  {
    text: "MITRE Corporation, Cursor-on-Target (CoT) Message Router User's Guide; ATAK CoT conventions.",
    note: "Track-to-CoT adapter (penumbra/c2/cot.py) event schema and type-code mapping.",
  },
];

export function References() {
  return (
    <>
      <section className="section" style={{ paddingTop: 48 }}>
        <div className="container">
          <div className="eyebrow">References</div>
          <h1>Every physics claim in this webapp traces to a checkable source.</h1>
          <p style={{ maxWidth: 720 }}>
            Each entry below was checked against its publisher or arXiv record before being relied
            on here. Broadcast tower EIRP/HAAT figures (CBOT-DT, CHOT-DT, CFGS-DT) are cited
            in-line on the <a href="/architecture">Architecture</a> page from Wikipedia and CRTC
            public records and should be re-verified against the ISED broadcast database before any
            real deployment, exactly as the program's own red-team ledger requires.
          </p>
          <ul className="citation-list" style={{ marginTop: 24 }}>
            {CITATIONS.map((c, i) => (
              <li key={i}>
                {c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.text}</a> : c.text}
                <div style={{ color: "var(--text-faint)", fontSize: "0.82rem", marginTop: 4 }}>{c.note}</div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section" style={{ borderBottom: "none" }}>
        <div className="container">
          <div className="eyebrow">Image credits</div>
          <h2>All photography is openly licensed and credited.</h2>
          <p style={{ maxWidth: 720 }}>
            No stock photography or AI-generated imagery is used. Every photograph is sourced from
            Wikimedia Commons under a Creative Commons license that permits reuse with attribution.
          </p>
          <div className="grid grid-2" style={{ marginTop: 16 }}>
            {IMAGE_CREDITS.map((c) => (
              <div className="panel" key={c.id}>
                <strong>{c.title}</strong>
                <p style={{ margin: "6px 0 0", fontSize: "0.88rem" }}>
                  {c.author} · <a href={c.licenseUrl} target="_blank" rel="noreferrer">{c.license}</a>
                  <br />
                  <a href={c.sourceUrl} target="_blank" rel="noreferrer">Source on Wikimedia Commons</a>
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
