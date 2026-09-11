import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { ToastProvider } from "../common/Toast";

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { pathname } = useLocation();

  return (
    <ToastProvider>
      <div className="app-shell">
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((prev) => !prev)}
          mobileOpen={mobileOpen}
          onMobileClose={() => setMobileOpen(false)}
        />

        {mobileOpen && (
          <div
            className="drawer-backdrop"
            style={{ zIndex: 25 }}
            onClick={() => setMobileOpen(false)}
          />
        )}

        <div className="app-shell__main">
          <Header onMobileMenuToggle={() => setMobileOpen((prev) => !prev)} />
          {/* key on pathname so the entrance animation replays on every
              navigation - without it React reuses the node and the transition
              only ever plays once, on first mount. */}
          <main className="app-shell__content agni-page-enter" key={pathname}>
            <Outlet />
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
