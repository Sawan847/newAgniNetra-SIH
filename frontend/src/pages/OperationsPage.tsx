import { useEffect, useState, useMemo, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { OrbitArtwork } from "../components/layout/OrbitArtwork";
import { CommandMap } from "../components/map/CommandMap";
import { Card, MetricCard } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { FireClassBadge } from "../components/common/Badge";
import { Drawer } from "../components/common/Drawer";
import { useToast } from "../components/common/Toast";
import { API_BASE, hotspotsApi, predictionsApi, alertsApi, facilitiesApi } from "../api/client";
import {
  FIRE_CLASS_COLORS,
  FIRE_CLASS_LABELS,
  type FireClass,
  type Hotspot,
  type IndustrialFacility,
} from "../types";

export function OperationsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { addToast } = useToast();

  const snapshotModeRef = useRef(false);
  const [snapshotMode, setSnapshotMode] = useState(false);
  const [snapshotDates, setSnapshotDates] = useState("");
  const [facilities, setFacilities] = useState<IndustrialFacility[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedHotspot, setSelectedHotspot] = useState<Hotspot | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [predicting, setPredicting] = useState(false);

  // Filters
  const [filterClass, setFilterClass] = useState<string>("all");
  const [minFrp, setMinFrp] = useState<number>(0);
  const [filterSatellite, setFilterSatellite] = useState<string>("all");
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showClusters, setShowClusters] = useState(false);

  // Historical Replay Timeline State
  const [replayMode, setReplayMode] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);
  const [replaySpeed, setReplaySpeed] = useState<number>(1);

  // Chronological sorting for historical timeline replay
  const sortedHotspots = useMemo(() => {
    return [...hotspots].sort((a, b) => {
      const timeA = `${a.acq_date || ""} ${a.acq_time || ""}`;
      const timeB = `${b.acq_date || ""} ${b.acq_time || ""}`;
      return timeA.localeCompare(timeB);
    });
  }, [hotspots]);

  const displayedHotspots = useMemo(() => {
    if (!replayMode) return hotspots;
    if (sortedHotspots.length === 0) return [];
    return sortedHotspots.slice(0, Math.min(replayIndex + 1, sortedHotspots.length));
  }, [replayMode, replayIndex, sortedHotspots, hotspots]);

  // Replay playback ticker
  useEffect(() => {
    if (!replayMode || !isPlaying) return;
    const interval = setInterval(() => {
      setReplayIndex((prev) => {
        if (prev >= sortedHotspots.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, 1200 / replaySpeed);
    return () => clearInterval(interval);
  }, [replayMode, isPlaying, replaySpeed, sortedHotspots.length]);

  // Named SSE events invalidate database results; snapshot observations stay dated.
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/events/stream`);
    const refresh = () => { if (!snapshotModeRef.current) fetchHotspots(); };
    es.addEventListener("hotspot_detected", refresh);
    return () => es.close();
  }, [filterClass, minFrp, filterSatellite, snapshotMode]);

  useEffect(() => {
    facilitiesApi.list({ per_page: 500 }).then(r => { if (!snapshotModeRef.current) setFacilities(r.data); })
      .catch(() => { if (!snapshotModeRef.current) setFacilities([]); });
  }, []);

  const fetchHotspots = () => {
    if (snapshotMode) return;
    setLoading(true);
    hotspotsApi
      .list({
        per_page: 250,
        min_frp: minFrp > 0 ? minFrp : undefined,
        satellite: filterSatellite !== "all" ? filterSatellite : undefined,
        fire_class: filterClass !== "all" ? filterClass : undefined,
      })
      .then((res) => { if (!snapshotModeRef.current) setHotspots(res.data || []); })
      .catch((err) => {
        if (!snapshotModeRef.current) addToast({ type: "danger", title: "Database unavailable", message: err.message });
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchHotspots();
  }, [filterClass, minFrp, filterSatellite, snapshotMode]);

  const loadSnapshot = async () => {
    setLoading(true);
    try {
      const response = await fetch("/data/observations.json");
      if (!response.ok) throw new Error("Snapshot unavailable. Run scripts/download_observations.py first.");
      const data = await response.json();
      snapshotModeRef.current = true;
      setSnapshotMode(true);
      setHotspots(data.hotspots);
      setFacilities(data.facilities);
      setSnapshotDates(`${data.manifest.min_acquisition_date} to ${data.manifest.max_acquisition_date}`);
      const nearest = [...data.hotspots].sort((a: Hotspot, b: Hotspot) =>
        ((a.longitude - 69.87) ** 2 + (a.latitude - 22.35) ** 2) -
        ((b.longitude - 69.87) ** 2 + (b.latitude - 22.35) ** 2))[0];
      setSelectedHotspot(nearest || null);
      setReplayMode(false);
      setIsPlaying(false);
    } catch (err) { addToast({ type: "danger", title: "Snapshot unavailable", message: err instanceof Error ? err.message : "Download failed" }); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    if (searchParams.get("snapshot") === "1") {
      void loadSnapshot();
      setSearchParams({}, { replace: true });
    }
  }, [searchParams]);

  const handleSelectHotspot = (h: Hotspot) => {
    setSelectedHotspot(h);
    setDrawerOpen(true);
  };

  const handleRunPredict = async () => {
    if (!selectedHotspot) return;
    if (snapshotMode) { addToast({ type: "info", title: "Observed snapshot", message: "Import the NASA CSV into the database to run enrichment or save alerts." }); return; }
    setPredicting(true);
    try {
      const res = await predictionsApi.predict(selectedHotspot.id);
      addToast({
        type: "success",
        title: res.data.confidence_score == null ? "Classification unavailable" : "Inference complete",
        message: res.data.confidence_score == null ? "No verified model is loaded. Observation remains uncertain." : `${FIRE_CLASS_LABELS[res.data.predicted_class]} (${Math.round(res.data.confidence_score * 100)}% model confidence)`,
      });

      // Update hotspot in list
      setHotspots((prev) =>
        prev.map((item) =>
          item.id === selectedHotspot.id
            ? {
                ...item,
                predicted_class: res.data.predicted_class,
                confidence_score: res.data.confidence_score,
              }
            : item,
        ),
      );

      setSelectedHotspot((prev) =>
        prev
          ? {
              ...prev,
              predicted_class: res.data.predicted_class,
              confidence_score: res.data.confidence_score,
            }
          : null,
      );
    } catch (err: unknown) {
      addToast({
        type: "danger",
        title: "Inference Failed",
        message: err instanceof Error ? err.message : "Error executing prediction pipeline",
      });
    } finally {
      setPredicting(false);
    }
  };

  const handleDispatchAlert = async () => {
    if (!selectedHotspot) return;
    if (snapshotMode) { addToast({ type: "info", title: "Observed snapshot", message: "Import the NASA CSV into the database to run enrichment or save alerts." }); return; }
    try {
      await alertsApi.create({
        hotspot_id: selectedHotspot.id,
        severity: "medium",
        alert_type: "analyst_review",
        status: "active",
        description: `Analyst review requested from Operations Console for coordinate (${selectedHotspot.latitude}, ${selectedHotspot.longitude})`,
      });
      addToast({
        type: "warning",
        title: "Review Alert Created",
        message: "Alert saved in the local review queue.",
      });
    } catch (err: unknown) {
      addToast({
        type: "danger",
        title: "Could not save review alert",
        message: err instanceof Error ? err.message : "Error saving review alert",
      });
    }
  };

  // Metrics summary (dynamically reacts to replay or filtered hotspots)
  const metrics = useMemo(() => {
    const total = displayedHotspots.length;
    const industrial = displayedHotspots.filter(
      (h) =>
        h.predicted_class === "accidental_industrial_fire" ||
        h.predicted_class === "persistent_industrial_source",
    ).length;
    const critical = displayedHotspots.filter(
      (h) => (h.frp ?? 0) > 150,
    ).length;
    const maxFrp = displayedHotspots.reduce((max, h) => Math.max(max, h.frp ?? 0), 0);

    return { total, industrial, critical, maxFrp };
  }, [displayedHotspots]);

  return (
    <div className="operations-page">
      <section className="observatory-hero" aria-labelledby="observatory-title">
        <div className="hero__copy">
          <div className="eyebrow hero__eyebrow">THE THERMAL OBSERVATORY <span>SIH / 26162</span></div>
          <h1 id="observatory-title" className="hero__title">See the heat.<br /><em>Understand the signal.</em></h1>
          <p className="hero__description">A wider perspective on industrial heat. Explore satellite observations, connect the context, and investigate what matters.</p>
          <div className="hero__sources"><span><i />NASA FIRMS</span><span><i />OPENSTREETMAP</span><span><i />SATELLITE CONTEXT</span></div>
        </div>
        <OrbitArtwork />
      </section>
      <div className="source-strip">
        <div className="source-strip__identity">
          <span className="source-strip__icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7"/></svg></span>
          <div>
            <div className="source-strip__title">{snapshotMode ? `NASA observation snapshot · ${snapshotDates}` : "Database observations"}</div>
            <div className="source-strip__caption">{snapshotMode ? "OBSERVED DATA / UNCLASSIFIED" : "POSTGIS WORKSPACE / IMPORT TO BEGIN"}</div>
          </div>
        </div>
        <div className="source-strip__actions">
          <Button size="sm" variant={snapshotMode ? "outline" : "primary"} onClick={loadSnapshot}>
            {snapshotMode ? "Reload Snapshot" : "Explore NASA + OSM snapshot"}
          </Button>
          {snapshotMode && <Button size="sm" variant="outline" onClick={() => {
            snapshotModeRef.current = false;
            setSnapshotMode(false); setHotspots([]); setReplayMode(false);
            setIsPlaying(false); setSelectedHotspot(null);
            facilitiesApi.list({ per_page: 500 }).then(r => setFacilities(r.data)).catch(() => setFacilities([]));
          }}>Return to Database</Button>}
          <Button size="sm" variant={snapshotMode ? "primary" : "outline"} onClick={() => navigate("/system")}>Import Data ↗</Button>
        </div>
      </div>
      {snapshotMode && <p className="snapshot-note">Actual NASA observations, unclassified. OSM facilities cover Jamnagar. Import the CSV into the database for filters, enrichment and saved actions.</p>}
      {/* KPI Header Grid */}
      <div className="metrics-grid">
        <MetricCard
          label="Displayed Thermal Detections"
          value={loading ? "..." : metrics.total}
          meta={snapshotMode ? "Dated NASA download · unclassified" : "Latest 250 matching observations"}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="m14 10 4-4m-8 8-4 4M6 3l3 3-3 3-3-3 3-3Zm12 12 3 3-3 3-3-3 3-3Z"/><path d="M16 3a6 6 0 0 1 5 5M3 16a6 6 0 0 0 5 5"/></svg>}
        />
        <MetricCard
          label="High-FRP Observations"
          value={loading ? "..." : metrics.critical}
          meta="FRP > 150 MW · screening threshold"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"><path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v1"/></svg>}
          trend={metrics.critical > 0 ? "up" : "neutral"}
        />
        <MetricCard
          label="Industrial Classifications"
          value={loading ? "..." : metrics.industrial}
          meta="Model predictions · not unique sites"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"><path d="M3 21V10l6 3V8l6 4V3h5l1 18H3Z"/><path d="M7 17v1m5-1v1m5-1v1"/></svg>}
        />
        <MetricCard
          label="Peak Radiative Power"
          value={loading ? "..." : `${Math.round(metrics.maxFrp)} MW`}
          meta="Highest thermal intensity"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2c2 5-4 6-2 10 2 0 4-3 4-5 4 3 6 8 3 12-3 4-10 3-12-1C2 12 8 6 13 2Z"/></svg>}
        />
      </div>

      {/* Operations Map Card with Top Controls */}
      <Card glass className="map-card">
        <div className="map-card__heading">
          <div><h2><span>01 /</span> Thermal activity map</h2><p>Satellite detections and mapped industrial infrastructure</p></div>
          <span className="map-card__tag">GEOSPATIAL VIEW</span>
        </div>
        <div className="map-toolbar">
          <div className="map-toolbar__filters">
            <div>
              <select
                className="form-select"
                disabled={snapshotMode}
                aria-label="Classification"
                value={filterClass}
                onChange={(e) => setFilterClass(e.target.value)}
                style={{ width: 195, height: 36, fontSize: "0.82rem" }}
              >
                <option value="all">All Classifications</option>
                {Object.entries(FIRE_CLASS_LABELS).map(([val, label]) => (
                  <option key={val} value={val}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <select
                className="form-select"
                disabled={snapshotMode}
                aria-label="Satellite"
                value={filterSatellite}
                onChange={(e) => setFilterSatellite(e.target.value)}
                style={{ width: 145, height: 36, fontSize: "0.82rem" }}
              >
                <option value="all">All Satellites</option>
                <option value="SNPP">VIIRS SNPP</option>
                <option value="NOAA20">NOAA-20</option>
                <option value="NOAA21">NOAA-21</option>
              </select>
            </div>

            <div className="frp-filter">
              <span className="text-xs text-muted font-semibold" style={{ letterSpacing: "0.04em" }}>MIN FRP:</span>
              <input
                type="range"
                min="0"
                max="250"
                step="25"
                disabled={snapshotMode}
                value={minFrp}
                onChange={(e) => setMinFrp(Number(e.target.value))}
                style={{ width: 90 }}
              />
              <span className="frp-filter__value">
                {minFrp} MW
              </span>
            </div>
          </div>

          <div className="map-toolbar__actions">
            <Button
              variant={replayMode ? "primary" : "outline"}
              size="sm"
              onClick={() => {
                setReplayMode((prev) => {
                  if (!prev) setReplayIndex(0);
                  setIsPlaying(false);
                  return !prev;
                });
              }}
            >
              {replayMode ? "Replay Active" : "Timeline Replay"}
            </Button>
            <Button
              variant={showHeatmap ? "primary" : "outline"}
              size="sm"
              onClick={() => setShowHeatmap((prev) => !prev)}
            >
              {showHeatmap ? "Heatmap Active" : "Heatmap"}
            </Button>
            <Button
              variant={showClusters ? "primary" : "outline"}
              size="sm"
              onClick={() => setShowClusters((prev) => !prev)}
            >
              {showClusters ? "Clustering Active" : "Cluster"}
            </Button>
            <Button variant="outline" size="sm" disabled={snapshotMode} onClick={fetchHotspots}>
              Refresh
            </Button>
          </div>
        </div>

        {replayMode && <div className="replay-controls">
          <Button size="sm" disabled={!sortedHotspots.length} onClick={() => setIsPlaying(p => !p)}>
            {isPlaying ? "Pause replay" : "Play timeline"}
          </Button>
          <input aria-label="Acquisition timeline" type="range" min={0} max={Math.max(0, sortedHotspots.length - 1)}
            value={replayIndex} onChange={e => { setIsPlaying(false); setReplayIndex(Number(e.target.value)); }} style={{ flex: 1 }} />
          <span className="text-xs">{sortedHotspots.length ? replayIndex + 1 : 0} / {sortedHotspots.length} · {sortedHotspots[replayIndex]?.acq_date} {sortedHotspots[replayIndex]?.acq_time} UTC</span>
          <select aria-label="Replay speed" value={replaySpeed} onChange={e => setReplaySpeed(Number(e.target.value))}>
            {[1, 2, 5].map(speed => <option key={speed} value={speed}>{speed}x</option>)}
          </select>
        </div>}
        {/* Map View */}
        <div className="map-viewport">
          <CommandMap
            facilities={facilities}
            hotspots={displayedHotspots}
            selectedHotspot={selectedHotspot}
            onSelectHotspot={handleSelectHotspot}
            showHeatmap={showHeatmap}
            showClusters={showClusters}
          />
        </div>

        <div className="map-legend">
          <span className="map-legend__label">CLASSIFICATION</span>
          {Object.entries(FIRE_CLASS_LABELS).map(([cls, label]) => (
            <div key={cls} className="map-legend__item">
              <span className="map-legend__dot" style={{ background: FIRE_CLASS_COLORS[cls as FireClass] }} />
              <span>{label}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Selected Incident Drawer */}
      <Drawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={
          selectedHotspot ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span>Thermal Incident Inspection</span>
              {selectedHotspot.predicted_class && (
                <FireClassBadge fireClass={selectedHotspot.predicted_class} size="sm" />
              )}
            </div>
          ) : (
            "Incident Details"
          )
        }
        subtitle={
          selectedHotspot
            ? `LAT ${selectedHotspot.latitude.toFixed(4)}°N • LON ${selectedHotspot.longitude.toFixed(4)}°E`
            : undefined
        }
        footer={
          selectedHotspot && (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={snapshotMode}
                onClick={() => navigate(`/investigate/${selectedHotspot.id}`)}
              >
                Full Dossier ➔
              </Button>
              <Button
                variant="danger"
                size="sm"
                disabled={snapshotMode}
                onClick={handleDispatchAlert}
              >
                Create review alert
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={snapshotMode}
                loading={predicting}
                onClick={handleRunPredict}
              >
                Run AI Inference
              </Button>
            </>
          )
        }
      >
        {selectedHotspot ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Quick Status Box */}
            <div
              style={{
                background: "var(--surface-subtle)",
                border: "1px solid var(--border-card)",
                borderRadius: 12,
                padding: 14,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span className="text-xs text-muted font-semibold">AI CLASSIFICATION</span>
                <span className="text-xs font-semibold">
                  {selectedHotspot.confidence_score != null
                    ? `${Math.round(selectedHotspot.confidence_score * 100)}% Confidence`
                    : "Not Classified Yet"}
                </span>
              </div>
              <div style={{ fontSize: "1.05rem", fontWeight: 700 }}>
                {selectedHotspot.predicted_class
                  ? FIRE_CLASS_LABELS[selectedHotspot.predicted_class]
                  : "Awaiting Machine Learning Analysis"}
              </div>
            </div>

            {/* Thermal Measurements Table */}
            <div>
              <h4 style={{ marginBottom: 8 }}>Thermal Measurements</h4>
              <div className="table-container">
                <table className="table">
                  <tbody>
                    <tr>
                      <td className="text-muted text-xs">Fire Radiative Power (FRP)</td>
                      <td className="font-bold">{selectedHotspot.frp != null ? `${selectedHotspot.frp} MW` : "N/A"}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Brightness (TI4)</td>
                      <td>{selectedHotspot.bright_ti4 ?? selectedHotspot.brightness ?? "N/A"} K</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Brightness (TI5)</td>
                      <td>{selectedHotspot.bright_ti5 ?? "N/A"} K</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Detection Confidence</td>
                      <td>{selectedHotspot.confidence != null ? `${selectedHotspot.confidence} (source encoding)` : "N/A"}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Satellite Sensor</td>
                      <td>{selectedHotspot.satellite ?? "VIIRS"}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Acquisition Time</td>
                      <td>
                        {selectedHotspot.acq_date ?? "N/A"} {selectedHotspot.acq_time ?? ""} (
                        {selectedHotspot.daynight === "N" ? "Night" : "Day"})
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            {/* Proximity & Context */}
            <div>
              <h4 style={{ marginBottom: 8 }}>Spatial Proximity Assessment</h4>
              <div
                style={{
                  background: "var(--surface-card)",
                  border: "1px solid var(--border-card)",
                  borderRadius: 12,
                  padding: 14,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  fontSize: "0.85rem",
                }}
              >
                <div>
                  <span className="text-muted">Proximity: </span>
                  <span className="font-semibold">Facility markers show OSM coverage; inspect enriched evidence after import</span>
                </div>
                <div>
                  <span className="text-muted">Sentinel-2 SR: </span>
                  <span className="font-semibold">Availability is checked during database enrichment</span>
                </div>
                <div>
                  <span className="text-muted">Event ID: </span>
                  <code style={{ fontSize: "0.75rem", background: "var(--surface-inset)", padding: "2px 6px", borderRadius: 4 }}>
                    {selectedHotspot.event_id || selectedHotspot.id.slice(0, 16)}
                  </code>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
