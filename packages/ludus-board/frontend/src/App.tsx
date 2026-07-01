import { NavLink, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="layout">
      <header className="topbar">
        <span className="brand">Ludus AI</span>
        <nav>
          <NavLink to="/scenarios">Scenarios</NavLink>
          <NavLink to="/targets">Targets</NavLink>
          <NavLink to="/runs">Runs</NavLink>
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
