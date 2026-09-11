import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { HealthIndicator } from "../health/HealthIndicator";
import { API_BASE, alertsApi } from "../../api/client";
import { useLanguage } from "../../i18n/LanguageContext";

interface HeaderProps {
  onMobileMenuToggle?: () => void;
}

export function Header({ onMobileMenuToggle }: HeaderProps) {
  const { language, setLanguage, t } = useLanguage();
  const [activeAlertsCount, setActiveAlertsCount] = useState<number>(0);
  const [sseConnected, setSseConnected] = useState<boolean>(false);

  useEffect(() => {
    alertsApi
      .list({ status: "active", per_page: 1 })
      .then((res) => {
        setActiveAlertsCount(res.meta?.total ?? res.data?.length ?? 0);
      })
      .catch(() => {
        // Silently handle if offline/initial loading
      });

    // Connect to Server-Sent Events stream
    let eventSource: EventSource | null = null;
    try {
      eventSource = new EventSource(`${API_BASE}/events/stream`);
      eventSource.onopen = () => setSseConnected(true);
      eventSource.onerror = () => setSseConnected(false);
      const refreshAlerts = () => {
        alertsApi.list({ status: "active", per_page: 1 }).then(res => setActiveAlertsCount(res.meta?.total ?? 0)).catch(() => {});
      };
      eventSource.addEventListener("alert_raised", refreshAlerts);
      eventSource.addEventListener("alert_updated", refreshAlerts);
    } catch {
      setSseConnected(false);
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, []);

  return (
    <>
      <header className="header">
        <div className="header__left">
          {onMobileMenuToggle && (
            <button
              className="btn btn--outline btn--icon"
              onClick={onMobileMenuToggle}
              aria-label="Toggle mobile menu"
              id="mobile-menu-btn"
            >
              ☰
            </button>
          )}
          <div className="header__badge">
            <span className={`pulse-dot ${sseConnected ? "pulse-dot--success" : "pulse-dot--warning"}`} />
            <span>SIH26162 · Prototype</span>
          </div>
          <div>
            <div className="header__title">
              {language === "hi" ? "अग्निनेत्र तापीय निगरानी" : "AgniNetra Thermal Observatory"}
            </div>
            <div className="header__subtitle">
              {language === "hi"
                ? "औद्योगिक थर्मल बुद्धिमत्ता एवं दावानल वर्गीकरण प्रणाली"
                : "Industrial Thermal Intelligence & Wildfire Classification"}
            </div>
          </div>
        </div>

        <div className="header__right">
          <Link className="btn btn--outline btn--sm header__snapshot" to="/?snapshot=1">
            NASA + OSM snapshot
          </Link>

          <div className="language-switch" role="group" aria-label="Language">
            <button aria-pressed={language === "en"} onClick={() => setLanguage("en")}>EN</button>
            <button aria-pressed={language === "hi"} onClick={() => setLanguage("hi")}>हिन्दी</button>
          </div>

          <Link
            to="/alerts"
            className="btn btn--outline btn--sm"
            style={{
              borderColor: activeAlertsCount > 0 ? "rgba(239, 68, 68, 0.35)" : undefined,
              background: activeAlertsCount > 0 ? "var(--danger-subtle)" : undefined,
              color: activeAlertsCount > 0 ? "var(--danger)" : undefined,
            }}
          >
            {activeAlertsCount > 0 && <span className="pulse-dot pulse-dot--danger" />}
            <span>{t("header.alerts_active")}</span>
            {activeAlertsCount > 0 && (
              <span
                style={{
                  background: "var(--danger)",
                  color: "white",
                  borderRadius: "var(--radius-pill)",
                  padding: "1px 6px",
                  fontSize: "0.7rem",
                  fontWeight: 700,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {activeAlertsCount}
              </span>
            )}
          </Link>
          <HealthIndicator />
        </div>
      </header>
    </>
  );
}
