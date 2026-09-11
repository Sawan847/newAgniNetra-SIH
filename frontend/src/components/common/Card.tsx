import React from "react";
import { formatCounted, useCountUp } from "../../hooks/useCountUp";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glass?: boolean;
}

export function Card({
  glass = false,
  className = "",
  children,
  ...props
}: CardProps) {
  const glassClass = glass ? "card--glass" : "";
  return (
    <div className={`card ${glassClass} ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  action,
  subtitle,
  children,
  className = "",
}: {
  title?: React.ReactNode;
  action?: React.ReactNode;
  subtitle?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`card__header ${className}`}>
      {children ? (
        children
      ) : (
        <>
          <div>
            {title && <div className="card__title">{title}</div>}
            {subtitle && (
              <div className="text-xs text-muted" style={{ marginTop: 2 }}>
                {subtitle}
              </div>
            )}
          </div>
          {action && <div>{action}</div>}
        </>
      )}
    </div>
  );
}

/**
 * Animated numeric readout. Counts from the previous value to the new one, so a
 * figure arriving from the API reads as live telemetry rather than a static
 * screenshot. Falls through to plain rendering for anything non-numeric (a
 * loading ellipsis, an em dash, a formatted string).
 */
function AnimatedValue({
  value,
  suffix,
  decimals = 0,
}: {
  value: number;
  suffix?: string;
  decimals?: number;
}) {
  const counted = useCountUp(value);
  return (
    <span className="agni-count">
      {formatCounted(counted, decimals)}
      {suffix ? <span className="metric-card__suffix">{suffix}</span> : null}
    </span>
  );
}

export function MetricCard({
  label,
  value,
  meta,
  icon,
  trend,
  className = "",
  animate = true,
  suffix,
  decimals = 0,
  critical = false,
}: {
  label: string;
  value: React.ReactNode;
  meta?: React.ReactNode;
  icon?: React.ReactNode;
  trend?: "up" | "down" | "neutral";
  className?: string;
  /** Count the value up on change. Ignored when `value` is not a finite number. */
  animate?: boolean;
  /** Unit rendered after the number, e.g. "MW". Kept outside the counter so the
   *  unit does not animate along with the digits. */
  suffix?: string;
  decimals?: number;
  /** Adds the pulsing ring. Reserve this for states that need acting on now. */
  critical?: boolean;
}) {
  const numeric =
    animate && (typeof value === "number" || typeof value === "string")
      ? Number(value)
      : Number.NaN;
  const isCountable = animate && Number.isFinite(numeric);

  return (
    <Card className={`metric-card ${critical ? "agni-critical" : ""} ${className}`}>
      <div className="metric-card__top">
        <span className="metric-card__label">{label}</span>
        {icon && <div className="metric-card__icon" aria-hidden="true">{icon}</div>}
      </div>
      <div className="metric-card__value">
        {isCountable ? (
          <AnimatedValue value={numeric} suffix={suffix} decimals={decimals} />
        ) : (
          <>
            {value}
            {suffix ? <span className="metric-card__suffix">{suffix}</span> : null}
          </>
        )}
      </div>
      {meta && <div className="metric-card__meta">
        {trend === "up" && <span className="metric-card__indicator metric-card__indicator--warm" aria-hidden="true" />}
        {trend === "down" && <span className="metric-card__indicator" aria-hidden="true" />}
        <span>{meta}</span>
      </div>}
    </Card>
  );
}
