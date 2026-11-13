import { useEffect, type ReactNode } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { loadSession } from "./lib/auth";
import { desktop, parseDeepLink } from "./lib/desktop";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Models from "./pages/Models";
import Soon from "./pages/Soon";
import Wallet from "./pages/Wallet";

const SOON_PATHS = ["/agents", "/connections", "/runs"];

function RequireAuth({ children }: { children: ReactNode }) {
  return loadSession() ? <>{children}</> : <Navigate to="/login" replace />;
}

/** `kaarvand://wallet?status=paid` (the gateway return) -> in-app route. */
function DeepLinkBridge() {
  const navigate = useNavigate();

  useEffect(() => {
    const bridge = desktop();
    if (!bridge?.onDeepLink) return;
    return bridge.onDeepLink((url) => {
      const { path, params } = parseDeepLink(url);
      const query = params.toString();
      navigate(query ? `${path}?${query}` : path, { replace: true });
    });
  }, [navigate]);

  return null;
}

export default function App() {
  return (
    <>
      <DeepLinkBridge />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Home />
            </RequireAuth>
          }
        />
        <Route
          path="/wallet"
          element={
            <RequireAuth>
              <Wallet />
            </RequireAuth>
          }
        />
        <Route
          path="/models"
          element={
            <RequireAuth>
              <Models />
            </RequireAuth>
          }
        />
        {SOON_PATHS.map((path) => (
          <Route
            key={path}
            path={path}
            element={
              <RequireAuth>
                <Soon />
              </RequireAuth>
            }
          />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

