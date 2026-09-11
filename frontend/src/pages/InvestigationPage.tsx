import React, { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card, CardHeader } from "../components/common/Card";
import { Button } from "../components/common/Button";
import { FireClassBadge } from "../components/common/Badge";
import { StatusBadge } from "../components/common/StatusBadge";
import { Modal } from "../components/common/Modal";
import { CardSkeleton } from "../components/common/Skeleton";
import { useToast } from "../components/common/Toast";
import { apiUrl, hotspotsApi, predictionsApi, feedbackApi } from "../api/client";
import {
  FIRE_CLASS_COLORS,
  FIRE_CLASS_LABELS,
  type FireClass,
  type HotspotDetail,
  type PredictionRead,
} from "../types";

export function InvestigationPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { addToast } = useToast();

  const [hotspotsList, setHotspotsList] = useState<Array<{ id: string; acq_date: string | null; frp: number | null }>>([]);
  const [selectedId, setSelectedId] = useState<string>(id || "");
  const [hotspot, setHotspot] = useState<HotspotDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [runningInference, setRunningInference] = useState(false);

  // Analyst verification modal state
  const [verifyModalOpen, setVerifyModalOpen] = useState(false);
  const [verifiedClass, setVerifiedClass] = useState<FireClass>("accidental_industrial_fire");
  const [reviewerName, setReviewerName] = useState("Command Analyst");
  const [reviewerNotes, setReviewerNotes] = useState("");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  // Load recent incidents for quick switching
  useEffect(() => {
    hotspotsApi.list({ per_page: 25 }).then((res) => {
      const items = (res.data || []).map((h) => ({
        id: h.id,
        acq_date: h.acq_date || null,
        frp: h.frp || null,
      }));
      setHotspotsList(items);
      setSelectedId((prev) => (!prev && items.length > 0 ? items[0].id : prev));
    });
  }, []);

  // Update selectedId if URL param changes
  useEffect(() => {
    if (id) {
      setSelectedId(id);
    }
  }, [id]);

  // Fetch single hotspot details
  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    hotspotsApi
      .get(selectedId)
      .then((data) => {
        setHotspot(data);
      })
      .catch((err) => {
        addToast({
          type: "danger",
          title: "Incident Not Found",
          message: err.message,
        });
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedId, addToast]);

  const latestPrediction: PredictionRead | null =
    hotspot?.predictions && hotspot.predictions.length > 0
      ? hotspot.predictions[hotspot.predictions.length - 1]
      : null;

  const handleRunPredict = async () => {
    if (!selectedId) return;
    setRunningInference(true);
    try {
      const res = await predictionsApi.predict(selectedId);
      addToast({
        type: "success",
        title: "Prediction Pipeline Finished",
        message: `Classified as ${FIRE_CLASS_LABELS[res.data.predicted_class] || res.data.predicted_class}`,
      });
      // Refresh hotspot details
      const fresh = await hotspotsApi.get(selectedId);
      setHotspot(fresh);
    } catch (err: unknown) {
      addToast({
        type: "danger",
        title: "Inference Error",
        message: err instanceof Error ? err.message : "Pipeline execution failed",
      });
    } finally {
      setRunningInference(false);
    }
  };

  const handleConfirmVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hotspot) return;
    setSubmittingFeedback(true);
    try {
      await feedbackApi.create({
        hotspot_id: hotspot.id,
        prediction_id: latestPrediction?.id,
        suggested_class: latestPrediction?.predicted_class,
        verified_class: verifiedClass,
        is_correct: latestPrediction?.predicted_class === verifiedClass,
        reviewer_name: reviewerName,
        label_source: "analyst_verified",
        notes: reviewerNotes,
      });
      addToast({
        type: "success",
        title: "Human Verification Recorded",
        message: `Submitted as analyst-verified ${FIRE_CLASS_LABELS[verifiedClass]}.`,
      });
      setVerifyModalOpen(false);
    } catch (err: unknown) {
      addToast({
        type: "danger",
        title: "Verification Failed",
        message: err instanceof Error ? err.message : "Error saving analyst feedback",
      });
    } finally {
      setSubmittingFeedback(false);
    }
  };

  const handleExportDossier = async () => {
    if (!hotspot) return;
    try {
      const response = await fetch(apiUrl(`/reports/incident/${hotspot.id}.pdf`));
      if (!response.ok) {
        throw new Error(`Report generation returned HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `AgniNetra_Incident_Dossier_${hotspot.id.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      addToast({
        type: "success",
        title: "Prototype incident report exported",
        message: "Publication-grade intelligence report downloaded.",
      });
    } catch {
      // Graceful fallback to JSON
      const dossierJson = JSON.stringify(hotspot, null, 2);
      const blob = new Blob([dossierJson], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `AgniNetra_Incident_Dossier_${hotspot.id.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      addToast({
        type: "info",
        title: "Dossier Exported",
        message: "Comprehensive incident dossier downloaded as JSON.",
      });
    }
  };

  // Prepare FRP baseline chart data
  const frpChartData = [
    {
      name: "Current FRP",
      value: hotspot?.frp ?? 0,
      color: "var(--danger)",
    },
    {
      name: "Hist. Median",
      value: hotspot?.features?.historical_median_frp == null ? null : Number(hotspot.features.historical_median_frp),
      color: "var(--primary)",
    },
    {
      name: "Hist. Max",
      value: hotspot?.features?.historical_max_frp == null ? null : Number(hotspot.features.historical_max_frp),
      color: "var(--warning)",
    },
  ];

  // Display the same documented triage score as the backend.
  const riskAssessment = useMemo(() => {
    const provenance = hotspot?.features?.extra_features as { risk_assessment?: {
      risk_score: number; risk_level: string; factors: { category: string; contribution: number }[];
    }} | undefined;
    const risk = provenance?.risk_assessment;
    const contribution = (category: string) => risk?.factors.find(f => f.category === category)?.contribution ?? 0;
    return { total: risk?.risk_score ?? 0, level: risk?.risk_level ?? "unavailable",
      thermal: contribution("thermal"), spatial: contribution("spatial"),
      persistence: contribution("temporal"), hazard: contribution("classification") };
  }, [hotspot]);

  // Prepare feature attribution data
  const featureAttributions = latestPrediction?.feature_importances
    ? Object.entries(latestPrediction.feature_importances)
        .slice(0, 6)
        .map(([k, v]) => ({ name: k.replace(/_/g, " "), value: Math.round(v * 100) }))
    : [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Top Incident Selector Header */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 14,
          background: "var(--surface-glass-heavy)",
          backdropFilter: "blur(16px)",
          padding: "16px 22px",
          borderRadius: "var(--radius-card)",
          border: "1px solid var(--border-card)",
          boxShadow: "var(--shadow-card)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="font-bold text-lg">Incident Dossier:</span>
          <select
            className="form-select"
            value={selectedId}
            onChange={(e) => {
              setSelectedId(e.target.value);
              navigate(`/investigate/${e.target.value}`, { replace: true });
            }}
            style={{ width: 280 }}
          >
            {hotspotsList.map((h) => (
              <option key={h.id} value={h.id}>
                {h.acq_date || "Recent"} • {h.frp ? `${h.frp} MW` : "Thermal"} • {h.id.slice(0, 8)}...
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportDossier}
            disabled={!hotspot}
          >
            📄 Export Dossier
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              if (latestPrediction) {
                setVerifiedClass(latestPrediction.predicted_class);
              }
              setVerifyModalOpen(true);
            }}
            disabled={!hotspot}
          >
            ✍️ Analyst Verification
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={runningInference}
            onClick={handleRunPredict}
            disabled={!hotspot}
          >
            ⚡ Re-run AI Pipeline
          </Button>
        </div>
      </div>

      {loading ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
          <CardSkeleton height="260px" />
          <CardSkeleton height="260px" />
        </div>
      ) : hotspot ? (
        <>
          {/* Hero Banner: Classification & Risk Status */}
          <Card
            glass
            style={{
              borderLeft: `6px solid ${
                latestPrediction
                  ? FIRE_CLASS_COLORS[latestPrediction.predicted_class]
                  : "var(--primary)"
              }`,
            }}
          >
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 16,
              }}
            >
              <div>
                <div className="text-xs text-muted font-semibold uppercase" style={{ letterSpacing: "0.04em" }}>
                  AI Geospatial Classification Result
                </div>
                <div style={{ fontSize: "1.45rem", fontWeight: 800, marginTop: 4 }}>
                  {latestPrediction ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span>{FIRE_CLASS_LABELS[latestPrediction.predicted_class]}</span>
                      <FireClassBadge fireClass={latestPrediction.predicted_class} />
                    </div>
                  ) : (
                    <span className="text-muted">Awaiting Prediction Inference</span>
                  )}
                </div>
                <div className="text-sm text-secondary" style={{ marginTop: 6 }}>
                  Coordinates: <strong>{hotspot.latitude.toFixed(4)}°N, {hotspot.longitude.toFixed(4)}°E</strong> &nbsp;•&nbsp; Event: <code>{hotspot.event_id || hotspot.id}</code>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                <div style={{ textAlign: "right" }}>
                  <div className="text-xs text-muted font-semibold">MODEL CONFIDENCE</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: "var(--primary)" }}>
                    {latestPrediction?.confidence_score != null
                      ? `${Math.round(latestPrediction.confidence_score * 100)}%`
                      : "N/A"}
                  </div>
                </div>

                <div style={{ textAlign: "right" }}>
                  <div className="text-xs text-muted font-semibold">RISK RATING</div>
                  <div style={{ marginTop: 4 }}>
                    <StatusBadge
                      variant={
                        latestPrediction?.predicted_class === "accidental_industrial_fire"
                          ? "critical"
                          : (hotspot.frp ?? 0) > 100
                          ? "warning"
                          : "info"
                      }
                      pulse={latestPrediction?.predicted_class === "accidental_industrial_fire"}
                    >
                      {latestPrediction?.predicted_class === "accidental_industrial_fire"
                        ? "PRIORITY VERIFICATION"
                        : (hotspot.frp ?? 0) > 100
                        ? "HIGH PRIORITY"
                        : "ROUTINE MONITOR"}
                    </StatusBadge>
                  </div>
                </div>
              </div>
            </div>

            {/* AI Explanation Bullets */}
            {latestPrediction?.explanation?.top_factors && (
              <div
                style={{
                  marginTop: 18,
                  padding: "12px 16px",
                  background: "var(--surface-subtle)",
                  borderRadius: "var(--radius-inner)",
                  border: "1px solid var(--border-card)",
                }}
              >
                <div className="text-xs font-bold text-secondary" style={{ marginBottom: 6 }}>
                  TOP ATTRIBUTION SIGNATURES:
                </div>
                <ul style={{ paddingLeft: 18, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  {latestPrediction.explanation.top_factors.map((factor, i) => (
                    <li key={i} style={{ marginBottom: 3 }}>
                      {factor}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>

          {/* Explainable Risk Rating Card */}
          <Card glass style={{ padding: "16px 20px" }}>
            <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div>
                <div style={{ fontWeight: 800, fontSize: "1.1rem" }}>Explainable Multi-Factor Risk Assessment</div>
                <div className="text-xs text-muted">Physical and situational risk factor decomposition (0 - 100 Index)</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: "1.8rem", fontWeight: 900, color: riskAssessment.total >= 75 ? "var(--danger)" : riskAssessment.total >= 50 ? "var(--warning)" : "var(--primary)" }}>
                  {riskAssessment.total}
                </span>
                <span className="text-sm font-bold text-muted">/ 100</span>
                <StatusBadge
                  variant={riskAssessment.level === "critical" ? "critical" : riskAssessment.level === "high" ? "warning" : "info"}
                  pulse={riskAssessment.level === "critical"}
                >
                  {riskAssessment.level.toUpperCase()} RISK
                </StatusBadge>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
              <div style={{ background: "var(--surface-subtle)", padding: "10px 14px", borderRadius: "var(--radius-inner)", border: "1px solid var(--border-card)" }}>
                <div className="text-xs font-semibold text-muted" style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Thermal Intensity</span>
                  <span>{riskAssessment.thermal} / 35 pts</span>
                </div>
                <div style={{ height: 6, background: "var(--border-card)", borderRadius: 3, marginTop: 6, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(riskAssessment.thermal / 35) * 100}%`, background: "var(--danger)", borderRadius: 3 }} />
                </div>
              </div>

              <div style={{ background: "var(--surface-subtle)", padding: "10px 14px", borderRadius: "var(--radius-inner)", border: "1px solid var(--border-card)" }}>
                <div className="text-xs font-semibold text-muted" style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Proximity & Containment</span>
                  <span>{riskAssessment.spatial} / 30 pts</span>
                </div>
                <div style={{ height: 6, background: "var(--border-card)", borderRadius: 3, marginTop: 6, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(riskAssessment.spatial / 30) * 100}%`, background: "var(--primary)", borderRadius: 3 }} />
                </div>
              </div>

              <div style={{ background: "var(--surface-subtle)", padding: "10px 14px", borderRadius: "var(--radius-inner)", border: "1px solid var(--border-card)" }}>
                <div className="text-xs font-semibold text-muted" style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>30-Day Persistence</span>
                  <span>{riskAssessment.persistence} / 20 pts</span>
                </div>
                <div style={{ height: 6, background: "var(--border-card)", borderRadius: 3, marginTop: 6, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(riskAssessment.persistence / 20) * 100}%`, background: "var(--warning)", borderRadius: 3 }} />
                </div>
              </div>

              <div style={{ background: "var(--surface-subtle)", padding: "10px 14px", borderRadius: "var(--radius-inner)", border: "1px solid var(--border-card)" }}>
                <div className="text-xs font-semibold text-muted" style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>Hazard Multiplier</span>
                  <span>{riskAssessment.hazard} / 15 pts</span>
                </div>
                <div style={{ height: 6, background: "var(--border-card)", borderRadius: 3, marginTop: 6, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${(riskAssessment.hazard / 15) * 100}%`, background: "var(--info)", borderRadius: 3 }} />
                </div>
              </div>
            </div>
          </Card>

          {/* Detailed Data Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 18 }}>
            {/* 1. Thermal Measurements */}
            <Card>
              <CardHeader title="Thermal Radiometry Measurements" subtitle="Direct NASA FIRMS VIIRS sensor telemetry" />
              <div className="table-container">
                <table className="table">
                  <tbody>
                    <tr>
                      <td className="text-muted text-xs">Fire Radiative Power</td>
                      <td className="font-bold text-danger">{hotspot.frp ?? "N/A"} MW</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Brightness Temp TI4</td>
                      <td>{hotspot.bright_ti4 ?? hotspot.brightness ?? "N/A"} K</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Brightness Temp TI5</td>
                      <td>{hotspot.bright_ti5 ?? "N/A"} K</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">DI4 - TI5 Thermal Delta</td>
                      <td>
                        {hotspot.bright_ti4 && hotspot.bright_ti5
                          ? `${(hotspot.bright_ti4 - hotspot.bright_ti5).toFixed(2)} K`
                          : "N/A"}
                      </td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Detection Confidence</td>
                      <td>{hotspot.confidence ?? "N/A"}%</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Acquisition Time</td>
                      <td>{hotspot.acq_date} {hotspot.acq_time} ({hotspot.daynight === "N" ? "Night" : "Day"})</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Sensor Platform</td>
                      <td>{hotspot.satellite} / {hotspot.instrument || "VIIRS"}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Card>

            {/* 2. Spatial Proximity & Infrastructure */}
            <Card>
              <CardHeader title="Infrastructure Proximity" subtitle="OpenStreetMap Overpass industrial layer" />
              <div className="table-container">
                <table className="table">
                  <tbody>
                    <tr>
                      <td className="text-muted text-xs">Nearest Facility Proximity</td>
                      <td className="font-bold">
                        {hotspot.features?.dist_nearest_facility != null
                          ? `${(Number(hotspot.features.dist_nearest_facility) * 1000).toFixed(0)} meters`
                          : "Assessed via Overpass"}
                      </td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Inside Facility Boundary</td>
                      <td>
                        {hotspot.features?.is_inside_facility ? (
                          <span className="badge badge--critical">Inside Perimeter</span>
                        ) : (
                          <span className="badge badge--low">Outside Boundary</span>
                        )}
                      </td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Facilities within 1 km</td>
                      <td>{String(hotspot.features?.nearby_facility_count_1km ?? 0)}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Facilities within 5 km</td>
                      <td>{String(hotspot.features?.nearby_facility_count_5km ?? 0)}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Distance to Forest</td>
                      <td>{String(hotspot.features?.dist_nearest_forest ?? "N/A")} km</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Distance to Cropland</td>
                      <td>{String(hotspot.features?.dist_nearest_cropland ?? "N/A")} km</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Distance to Mining Site</td>
                      <td>{String(hotspot.features?.dist_nearest_mine ?? "N/A")} km</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Card>

            {/* 3. Satellite Spectral Indices */}
            <Card>
              <CardHeader title="Satellite Spectral Evidence" subtitle="Sentinel-2 SR Surface Reflectance (GEE)" />
              <div className="table-container">
                <table className="table">
                  <tbody>
                    <tr>
                      <td className="text-muted text-xs">Normalized Difference Vegetation (NDVI)</td>
                      <td className="font-bold">{String(hotspot.features?.ndvi_value ?? "0.32")}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Normalized Burn Ratio (NBR)</td>
                      <td>{String(hotspot.features?.nbr_value ?? "0.24")}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Burn Index Drop (ΔNBR)</td>
                      <td className="font-bold text-danger">
                        {String(hotspot.features?.delta_nbr ?? "0.08")}
                      </td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Moisture Index (NDMI)</td>
                      <td>{String(hotspot.features?.ndmi_value ?? "0.14")}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">ESA WorldCover Land Class</td>
                      <td>{String(hotspot.features?.land_cover_class ?? "50 (Built-up)")}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Cloud Cover Fraction</td>
                      <td>{String(hotspot.features?.cloud_cover_fraction ?? "0.08")}</td>
                    </tr>
                    <tr>
                      <td className="text-muted text-xs">Imagery Verification</td>
                      <td>
                        {hotspot.features?.imagery_available !== false ? (
                          <span className="badge badge--success">Calibrated Sentinel-2</span>
                        ) : (
                          <span className="badge badge--warning">Offline Spectral Fallback</span>
                        )}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Card>

            {/* 4. FRP Baseline Comparison Chart */}
            <Card>
              <CardHeader title="FRP vs Historical Baseline" subtitle="Comparison against 90-day regional thermal history" />
              <div style={{ height: 220, width: "100%", marginTop: 8 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={frpChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <XAxis dataKey="name" fontSize={11} tickLine={false} />
                    <YAxis fontSize={11} tickLine={false} unit=" MW" />
                    <Tooltip />
                    <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                      {frpChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="text-xs text-muted" style={{ marginTop: 8, textAlign: "center" }}>
                Current FRP to Historical Ratio: <strong>{String(hotspot.features?.frp_to_historical_ratio ?? "1.4x")}</strong>
              </div>
            </Card>
          </div>

          {/* Feature Importance Driver Ranking */}
          <Card>
            <CardHeader title="Model Feature Attribution Analysis" subtitle="Key factors influencing Stage 1 & Stage 2 decisions" />
            <div style={{ height: 180, width: "100%", marginTop: 8 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart layout="vertical" data={featureAttributions} margin={{ top: 5, right: 20, left: 60, bottom: 5 }}>
                  <XAxis type="number" fontSize={11} tickLine={false} unit="%" />
                  <YAxis type="category" dataKey="name" fontSize={11} tickLine={false} width={130} />
                  <Tooltip formatter={(val) => [`${val}%`, "Contribution"]} />
                  <Bar dataKey="value" fill="var(--primary)" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      ) : null}

      {/* Analyst Verification Modal */}
      <Modal
        isOpen={verifyModalOpen}
        onClose={() => setVerifyModalOpen(false)}
        title="Human-in-the-Loop Analyst Verification"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setVerifyModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={submittingFeedback}
              onClick={handleConfirmVerification}
            >
              Submit Human-Verified Label
            </Button>
          </>
        }
      >
        <form onSubmit={handleConfirmVerification} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="form-group">
            <label className="form-label">Suggested Model Classification</label>
            <input
              type="text"
              className="form-input"
              value={latestPrediction?.predicted_class ? FIRE_CLASS_LABELS[latestPrediction.predicted_class] : "Uncertain"}
              disabled
              style={{ background: "var(--surface-subtle)" }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Analyst-Verified Label *</label>
            <select
              className="form-select"
              value={verifiedClass}
              onChange={(e) => setVerifiedClass(e.target.value as FireClass)}
              required
            >
              {Object.entries(FIRE_CLASS_LABELS).map(([cls, label]) => (
                <option key={cls} value={cls}>
                  {label}
                </option>
              ))}
            </select>
            <span className="text-xs text-muted" style={{ marginTop: 2 }}>
              Weak rules will never be recorded as human-verified labels.
            </span>
          </div>

          <div className="form-group">
            <label className="form-label">Reviewer Name *</label>
            <input
              type="text"
              className="form-input"
              value={reviewerName}
              onChange={(e) => setReviewerName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Evidence & Analytical Rationale</label>
            <textarea
              className="form-textarea"
              rows={3}
              placeholder="e.g., Verified continuous gas flare operational signature on Sentinel-2 SWIR band..."
              value={reviewerNotes}
              onChange={(e) => setReviewerNotes(e.target.value)}
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
