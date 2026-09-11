import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, MetricCard, CardHeader } from "../components/common/Card";
import { CardSkeleton } from "../components/common/Skeleton";
import { useToast } from "../components/common/Toast";
import { modelApi } from "../api/client";
import type { ModelMetrics } from "../types";

export function ModelIntelligencePage() {
  const { addToast } = useToast();
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    modelApi
      .metrics()
      .then((res) => {
        setMetrics(res);
      })
      .catch((err) => {
        addToast({
          type: "danger",
          title: "Model Metrics Offline",
          message: err.message,
        });
      })
      .finally(() => {
        setLoading(false);
      });
  }, [addToast]);

  const evalMetrics = metrics?.evaluation_metrics || {};

  // Format feature importance for horizontal bar chart
  const importanceData = metrics?.feature_importances
    ? Object.entries(metrics.feature_importances)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10)
        .map(([name, weight]) => ({
          name: name.replace(/_/g, " "),
          weight: Math.round(weight * 1000) / 10,
        }))
    : [];

  const confusionMatrix = evalMetrics.confusion_matrix || [];

  const classLabels = [
    "Industrial Accidental",
    "Persistent Flare",
    "Wildfire",
    "Stubble Burning",
    "Mining",
    "Uncertain",
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      {/* KPI Evaluation Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 14 }}>
        <MetricCard
          label="Holdout Macro F1 Score"
          value={loading ? "..." : (evalMetrics.macro_f1 !== undefined ? `${(evalMetrics.macro_f1 * 100).toFixed(1)}%` : "Not evaluated")}
          meta="Chronological unseen holdout split"
          icon="🎯"
          trend="up"
        />
        <MetricCard
          label="Holdout Accuracy"
          value={loading ? "..." : (evalMetrics.accuracy !== undefined ? `${(evalMetrics.accuracy * 100).toFixed(1)}%` : "Not evaluated")}
          meta="Multi-class balanced evaluation"
          icon="📊"
        />
        <MetricCard
          label="Spatial GroupKFold F1"
          value={loading ? "..." : (evalMetrics.mean_spatial_cv_f1 !== undefined ? `${(evalMetrics.mean_spatial_cv_f1 * 100).toFixed(1)}%` : "Not evaluated")}
          meta="5-fold spatial cluster validation"
          icon="🌐"
        />
        <MetricCard
          label="False Alert Rate"
          value={loading ? "..." : (evalMetrics.false_alert_rate_industrial_fire !== undefined ? `${(evalMetrics.false_alert_rate_industrial_fire * 100).toFixed(2)}%` : "Not evaluated")}
          meta="False positive industrial alerts"
          icon="🛡️"
        />
      </div>

      {/* Honest Limitations & Architecture Banner */}
      <div
        style={{
          background: "linear-gradient(135deg, rgba(29, 78, 216, 0.06) 0%, rgba(13, 148, 136, 0.06) 100%)",
          border: "1px solid var(--primary-border)",
          borderRadius: "var(--radius-card)",
          padding: "16px 20px",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="badge badge--success">{metrics?.status === "ready" ? "TRAINED ARTIFACT" : "AWAITING VERIFIED TRAINING DATA"}</span>
            <span className="font-bold">{metrics?.active_model_name || "No verified model installed"}</span>
            <span className="text-xs text-muted">v{metrics?.version || "0"}</span>
          </div>
          <div className="text-xs text-secondary" style={{ marginTop: 4 }}>
            Two-stage hierarchical classifier: Stage 1 macro domain separation + Stage 2 industrial flare vs accidental fire classification with probability calibration.
          </div>
        </div>

        <div className="text-xs text-muted" style={{ textAlign: "right" }}>
          Uncertainty Cutoff: <strong>&tau; &lt; 0.45</strong> &nbsp;•&nbsp; Features: <strong>37 Dimensions</strong>
        </div>
      </div>

      {loading ? (
        <CardSkeleton height="360px" />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 18 }}>
          {/* Top 10 Feature Importances */}
          <Card>
            <CardHeader
              title="Top 10 Attribution Drivers"
              subtitle="Normalized feature importance from Stage 1 & Stage 2 models"
            />
            <div style={{ height: 280, width: "100%", marginTop: 10 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  layout="vertical"
                  data={importanceData}
                  margin={{ top: 5, right: 30, left: 70, bottom: 5 }}
                >
                  <XAxis type="number" fontSize={11} tickLine={false} unit="%" />
                  <YAxis type="category" dataKey="name" fontSize={11} tickLine={false} width={150} />
                  <Tooltip formatter={(val) => [`${val}%`, "Importance Weight"]} />
                  <Bar dataKey="weight" fill="var(--primary)" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Confusion Matrix Interactive Grid */}
          <Card>
            <CardHeader
              title="Multi-Class Confusion Matrix"
              subtitle="Holdout cross-validation accuracy per operational category"
            />
            <div className="table-container" style={{ marginTop: 8 }}>
              <table className="table" style={{ fontSize: "0.75rem", textAlign: "center" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left" }}>Actual \ Pred</th>
                    {classLabels.map((lbl, idx) => (
                      <th key={idx} style={{ padding: "8px 6px" }}>{lbl.slice(0, 8)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {confusionMatrix.map((row, rIdx) => (
                    <tr key={rIdx}>
                      <td style={{ textAlign: "left", fontWeight: 700 }}>{classLabels[rIdx]}</td>
                      {row.map((val, cIdx) => {
                        const isDiag = rIdx === cIdx;
                        return (
                          <td
                            key={cIdx}
                            style={{
                              background: isDiag ? "rgba(22, 163, 74, 0.15)" : val > 0 ? "rgba(234, 88, 12, 0.10)" : "transparent",
                              fontWeight: isDiag ? 800 : 400,
                              color: isDiag ? "var(--success)" : val > 0 ? "var(--warning)" : "var(--text-muted)",
                            }}
                          >
                            {val}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="text-xs text-muted" style={{ marginTop: 10, textAlign: "center" }}>
              {confusionMatrix.length ? "Rows are reference labels; columns are model predictions." : "No measured confusion matrix available. Train on verified observations first."}
            </div>
          </Card>
        </div>
      )}

      {/* Methodological Rigor & Data Leakage Safeguards */}
      <Card>
        <CardHeader
          title="Methodological Rigor & Scientific Safeguards"
          subtitle="Evaluation method and remaining validation requirements"
        />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
          <div
            style={{
              padding: 14,
              background: "var(--surface-subtle)",
              borderRadius: "var(--radius-inner)",
              border: "1px solid var(--border-card)",
            }}
          >
            <div className="font-bold text-sm" style={{ color: "var(--primary)", marginBottom: 4 }}>
              1. Spatial GroupKFold Cross-Validation
            </div>
            <div className="text-xs text-secondary">
              Use held-out facility or geographic groups for model selection. FIRMS detections and OSM tags do not provide ground-truth incident labels.
            </div>
          </div>

          <div
            style={{
              padding: 14,
              background: "var(--surface-subtle)",
              borderRadius: "var(--radius-inner)",
              border: "1px solid var(--border-card)",
            }}
          >
            <div className="font-bold text-sm" style={{ color: "var(--secondary)", marginBottom: 4 }}>
              2. Strict Chronological 15% Holdout
            </div>
            <div className="text-xs text-secondary">
              Reserve the latest acquisition dates for evaluation. Detection-time features use strictly prior observations; independent event and region holdouts are also needed.
            </div>
          </div>

          <div
            style={{
              padding: 14,
              background: "var(--surface-subtle)",
              borderRadius: "var(--radius-inner)",
              border: "1px solid var(--border-card)",
            }}
          >
            <div className="font-bold text-sm" style={{ color: "var(--warning)", marginBottom: 4 }}>
              3. Honest Uncertainty Thresholding
            </div>
            <div className="text-xs text-secondary">
              The classifier abstains below its confidence threshold. Missing or unverified model artifacts return Uncertain. Confidence requires validation on real, independently labelled incidents.
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
