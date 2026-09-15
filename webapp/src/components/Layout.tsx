import { NavLink, Outlet } from "react-router-dom";

const NAV_LINKS = [
  { to: "/", label: "Overview", end: true },
  { to: "/architecture", label: "Architecture" },
  { to: "/simulator", label: "Link-Budget Simulator" },
  { to: "/coverage", label: "Coverage" },
  { to: "/hardware", label: "Hardware" },
  { to: "/evidence", label: "Evidence & Tracking" },
  { to: "/program", label: "Program" },
  { to: "/references", label: "References" },
];

export function Layout() {
  return (
    <>
      <header className="site-header">
        <div className="container header-inner">
          <NavLink to="/" className="wordmark">
            <span className="wordmark-mark" aria-hidden="true" />
            PENUMBRA
          </NavLink>
          <nav className="site-nav">
            {NAV_LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => (isActive ? "active" : "")}>
                {l.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main style={{ flex: 1 }}>
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="container footer-inner">
          <div>
            <strong>PENUMBRA</strong>
            <p style={{ margin: "6px 0 0", maxWidth: 460 }}>
              A passive multistatic RF sensing mesh for urban counter-UAS. Technical concept and
              R&D program prepared for the Canadian DND/CAF IDEaS CUAS Urban Sandbox context.
              Detection and tracking only.
            </p>
          </div>
          <div className="footer-links">
            <NavLink to="/references">References &amp; image credits</NavLink>
            <a href="https://www.canada.ca/en/department-national-defence/programs/defence-ideas/element/sandboxes/challenge/counter-uncrewed-aerial-systems-urban-sandbox-2027.html" target="_blank" rel="noreferrer">
              DND IDEaS CUAS Sandbox
            </a>
          </div>
        </div>
      </footer>
    </>
  );
}
