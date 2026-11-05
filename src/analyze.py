"""Reproducible quality analysis for the Natural State sensor-network exercise.

Usage (from repository root):
    python src/analyze.py --input-dir data/raw --output-dir outputs

The script keeps raw gateway receptions separate from deduplicated uplink events.
A message heard by two gateways is one device transmission, not two sensor reports.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

LOG = logging.getLogger("sensor_audit")
EXPECTED_MINUTES = {
    "soil_moisture": 15,
    "weather": 15,
    "water_level": 15,
    "gps_collar": 60,
}
SENSOR_VALUE_COLUMNS = [
    "soil_moisture_pct", "temperature_c", "rainfall_mm", "water_level_cm"
]
GPS_COLUMNS = ["latitude", "longitude"]
DEPLOYMENT_START = pd.Timestamp("2026-03-02T00:00:00Z")
DEPLOYMENT_END_EXCLUSIVE = pd.Timestamp("2026-04-13T00:00:00Z")


def read_inputs(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Read the four source CSVs and parse timestamp columns as UTC."""
    required = {
        "devices.csv": {"device_id", "device_type", "model", "firmware_version", "expected_gateway"},
        "telemetry.csv": {"timestamp", "device_id", "gateway_id", "message_counter", "battery_v", "solar_current_ma"},
        "gateway_status.csv": {"timestamp", "gateway_id", "status", "backhaul", "battery_v", "messages_received"},
        "maintenance_log.csv": {"date", "device_id", "action"},
    }
    frames: dict[str, pd.DataFrame] = {}
    for name, columns in required.items():
        path = input_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Required input file not found: {path}")
        frame = pd.read_csv(path)
        missing = columns - set(frame.columns)
        if missing:
            raise ValueError(f"{name} is missing required columns: {sorted(missing)}")
        frames[name] = frame

    frames["telemetry.csv"]["timestamp"] = pd.to_datetime(
        frames["telemetry.csv"]["timestamp"], utc=True, errors="coerce"
    )
    frames["gateway_status.csv"]["timestamp"] = pd.to_datetime(
        frames["gateway_status.csv"]["timestamp"], utc=True, errors="coerce"
    )
    frames["maintenance_log.csv"]["date"] = pd.to_datetime(
        frames["maintenance_log.csv"]["date"], errors="coerce"
    )
    if frames["telemetry.csv"]["timestamp"].isna().any():
        raise ValueError("telemetry.csv contains unparseable timestamps")
    return (
        frames["devices.csv"], frames["telemetry.csv"],
        frames["gateway_status.csv"], frames["maintenance_log.csv"]
    )


def deduplicate_uplinks(telemetry: pd.DataFrame) -> pd.DataFrame:
    """Return one row per device uplink, regardless of how many gateways heard it.

    This exercise's frame counters do not wrap within the six-week window. In a
    production system, include DevEUI, FCntUp, session/reset identity and a bounded
    time window in the idempotency key to handle counter resets and wraparound.
    """
    required = {"device_id", "message_counter", "timestamp"}
    missing = required - set(telemetry.columns)
    if missing:
        raise ValueError(f"Cannot deduplicate; missing columns: {sorted(missing)}")
    ordered = telemetry.sort_values(["timestamp", "gateway_id"])
    return ordered.drop_duplicates(["device_id", "message_counter"], keep="first").copy()


def expected_interval_minutes(device_type: str) -> int:
    """Expected report interval from the assignment's device classes."""
    if device_type not in EXPECTED_MINUTES:
        raise ValueError(f"No expected interval configured for device type: {device_type}")
    return EXPECTED_MINUTES[device_type]


def expected_message_count(device_type: str, start: pd.Timestamp = DEPLOYMENT_START,
                           end: pd.Timestamp = DEPLOYMENT_END_EXCLUSIVE) -> int:
    """Number of scheduled opportunities in the configured half-open interval."""
    interval = expected_interval_minutes(device_type)
    seconds = (end - start).total_seconds()
    if seconds <= 0:
        raise ValueError("end must be later than start")
    return int(math.ceil(seconds / (interval * 60)))


def safe_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.median()) if not values.empty else float("nan")


def device_metrics(devices: pd.DataFrame, telemetry: pd.DataFrame) -> pd.DataFrame:
    """Calculate deduplicated reporting, power, value and gateway metrics."""
    unique = deduplicate_uplinks(telemetry)
    in_window = unique[
        (unique.timestamp >= DEPLOYMENT_START) & (unique.timestamp < DEPLOYMENT_END_EXCLUSIVE)
    ].copy()
    raw_gateway = telemetry[
        (telemetry.timestamp >= DEPLOYMENT_START) & (telemetry.timestamp < DEPLOYMENT_END_EXCLUSIVE)
    ].drop_duplicates(["device_id", "message_counter", "gateway_id"])

    rows: list[dict[str, object]] = []
    for device in devices.itertuples(index=False):
        events = in_window[in_window.device_id == device.device_id].sort_values("timestamp")
        receptions = raw_gateway[raw_gateway.device_id == device.device_id]
        expected_minutes = EXPECTED_MINUTES.get(device.device_type)
        expected_n = expected_message_count(device.device_type) if expected_minutes else np.nan
        intervals = events.timestamp.diff().dt.total_seconds().div(60).dropna()
        first = events.timestamp.min() if not events.empty else pd.NaT
        last = events.timestamp.max() if not events.empty else pd.NaT
        battery = pd.to_numeric(events.get("battery_v", pd.Series(dtype=float)), errors="coerce").dropna()
        solar = pd.to_numeric(events.get("solar_current_ma", pd.Series(dtype=float)), errors="coerce").dropna()
        recent_solar = pd.to_numeric(
            events.loc[events.timestamp >= DEPLOYMENT_END_EXCLUSIVE - pd.Timedelta(days=15), "solar_current_ma"],
            errors="coerce",
        ).dropna() if "solar_current_ma" in events else pd.Series(dtype=float)
        battery_n = max(1, int(math.ceil(len(battery) * 0.10))) if len(battery) else 0
        battery_start = float(battery.head(battery_n).median()) if battery_n else np.nan
        battery_end = float(battery.tail(battery_n).median()) if battery_n else np.nan
        invalid_mask = pd.Series(False, index=events.index)
        for column in SENSOR_VALUE_COLUMNS:
            if column in events:
                values = pd.to_numeric(events[column], errors="coerce")
                invalid_mask |= values.abs().gt(1_000_000)
        invalid_value_rows = int(invalid_mask.sum())
        first_invalid = events.loc[invalid_mask, "timestamp"].min() if invalid_value_rows else pd.NaT
        gps_zero = 0
        first_gps_zero = pd.NaT
        if device.device_type == "gps_collar" and set(GPS_COLUMNS).issubset(events.columns):
            gps_zero_mask = (pd.to_numeric(events.latitude, errors="coerce").eq(0) &
                             pd.to_numeric(events.longitude, errors="coerce").eq(0))
            gps_zero = int(gps_zero_mask.sum())
            first_gps_zero = events.loc[gps_zero_mask, "timestamp"].min() if gps_zero else pd.NaT
        expected_share = np.nan
        expected_rssi = np.nan
        expected_snr = np.nan
        strongest_gateway = ""
        strongest_rssi = np.nan
        if not receptions.empty:
            by_gateway = receptions.groupby("gateway_id").agg(
                rssi_median=("rssi_dbm", "median"), snr_median=("snr_db", "median")
            ) if {"rssi_dbm", "snr_db"}.issubset(receptions.columns) else pd.DataFrame()
            if not by_gateway.empty and by_gateway.rssi_median.notna().any():
                strongest_gateway = str(by_gateway.rssi_median.idxmax())
                strongest_rssi = float(by_gateway.loc[strongest_gateway, "rssi_median"])
            if pd.notna(device.expected_gateway):
                expected_receptions = receptions[receptions.gateway_id == device.expected_gateway]
                expected_share = float(len(expected_receptions) / len(receptions))
                expected_rssi = safe_median(expected_receptions.rssi_dbm) if "rssi_dbm" in expected_receptions else np.nan
                expected_snr = safe_median(expected_receptions.snr_db) if "snr_db" in expected_receptions else np.nan
        rain = pd.to_numeric(events.get("rainfall_mm", pd.Series(dtype=float)), errors="coerce").dropna()
        rows.append({
            "device_id": device.device_id,
            "device_type": device.device_type,
            "model": device.model,
            "firmware_version_registered": device.firmware_version,
            "expected_gateway": device.expected_gateway,
            "expected_interval_min": expected_minutes,
            "unique_uplinks": len(events),
            "expected_uplinks_42d": expected_n,
            "completeness_pct": (100 * len(events) / expected_n) if expected_n else np.nan,
            "median_interval_min": float(intervals.median()) if not intervals.empty else np.nan,
            "p95_interval_min": float(intervals.quantile(.95)) if not intervals.empty else np.nan,
            "max_gap_min": float(intervals.max()) if not intervals.empty else np.nan,
            "first_seen_utc": first.isoformat() if pd.notna(first) else "",
            "last_seen_utc": last.isoformat() if pd.notna(last) else "",
            "battery_min_v": float(battery.min()) if len(battery) else np.nan,
            "battery_start_median_v": battery_start,
            "battery_end_median_v": battery_end,
            "battery_change_v": battery_end - battery_start if battery_n else np.nan,
            "solar_median_ma": float(solar.median()) if len(solar) else np.nan,
            "solar_median_recent_15d_ma": float(recent_solar.median()) if len(recent_solar) else np.nan,
            "invalid_sentinel_rows": invalid_value_rows,
            "first_invalid_sensor_timestamp_utc": first_invalid.isoformat() if pd.notna(first_invalid) else "",
            "gps_zero_pair_rows": gps_zero,
            "first_gps_zero_timestamp_utc": first_gps_zero.isoformat() if pd.notna(first_gps_zero) else "",
            "gps_zero_pair_pct": (100 * gps_zero / len(events)) if len(events) else np.nan,
            "rainfall_nonzero_rows": int(rain.gt(0).sum()),
            "rainfall_observations": len(rain),
            "expected_gateway_reception_share_pct": 100 * expected_share if pd.notna(expected_share) else np.nan,
            "expected_gateway_rssi_median_dbm": expected_rssi,
            "expected_gateway_snr_median_db": expected_snr,
            "strongest_gateway_id": strongest_gateway,
            "strongest_gateway_rssi_median_dbm": strongest_rssi,
        })
    return pd.DataFrame(rows).sort_values("device_id")


def build_anomalies(summary: pd.DataFrame, devices: pd.DataFrame,
                    telemetry: pd.DataFrame, gateway_status: pd.DataFrame,
                    maintenance: pd.DataFrame) -> pd.DataFrame:
    """Create transparent candidate flags; human interpretation remains in report."""
    findings: list[dict[str, str]] = []

    def add(device_id: str, severity: str, flag: str, evidence: str) -> None:
        findings.append({"device_id": device_id, "severity": severity,
                         "flag": flag, "evidence": evidence})

    for row in summary.itertuples(index=False):
        if pd.notna(row.median_interval_min) and row.expected_interval_min and row.median_interval_min > row.expected_interval_min * 1.5:
            add(row.device_id, "high", "report_interval_too_slow",
                f"Median interval {row.median_interval_min:.1f} min; expected {row.expected_interval_min} min")
        if pd.notna(row.completeness_pct) and row.completeness_pct < 80:
            add(row.device_id, "high" if row.completeness_pct < 60 else "medium",
                "low_reporting_completeness", f"{row.completeness_pct:.1f}% of scheduled uplinks in 42-day window")
        if row.invalid_sentinel_rows:
            add(row.device_id, "critical", "impossible_sensor_sentinel",
                f"{row.invalid_sentinel_rows} rows contain an absolute sensor value above 1,000,000")
        if pd.notna(row.gps_zero_pair_pct) and row.gps_zero_pair_pct > 5:
            add(row.device_id, "high", "gps_zero_coordinate",
                f"{row.gps_zero_pair_pct:.1f}% of collar messages have (0, 0) coordinates")
        if pd.notna(row.battery_change_v) and row.battery_change_v <= -0.15:
            add(row.device_id, "high", "battery_downtrend",
                f"First-to-last decile median battery change {row.battery_change_v:.2f} V")
        if pd.notna(row.expected_gateway_reception_share_pct) and row.expected_gateway_reception_share_pct < 30:
            add(row.device_id, "medium", "weak_expected_gateway_path",
                f"Only {row.expected_gateway_reception_share_pct:.1f}% of gateway receptions came from expected gateway {row.expected_gateway}")
        if row.rainfall_observations >= 500 and row.rainfall_nonzero_rows == 0:
            add(row.device_id, "medium", "rainfall_flatline_check",
                f"{row.rainfall_observations} rainfall observations; all are zero")

    # Firmware outliers within a model family are prompts to validate the register,
    # not an automatic instruction to upgrade production devices.
    for model, group in devices.groupby("model"):
        modes = group.firmware_version.mode()
        if modes.empty:
            continue
        common = str(modes.iloc[0])
        for r in group[group.firmware_version.astype(str) != common].itertuples(index=False):
            add(r.device_id, "medium", "firmware_outlier_in_register",
                f"Registered {r.firmware_version}; modal firmware for {model} is {common}")

    # A maintenance log update can be newer than the static device register.
    import re
    for m in maintenance.itertuples(index=False):
        match = re.search(r"updated from\s+([\w.]+)\s+to\s+([\w.]+)", str(m.action), re.I)
        if match:
            registered = devices.loc[devices.device_id == m.device_id, "firmware_version"]
            if not registered.empty and str(registered.iloc[0]) != match.group(2):
                add(m.device_id, "medium", "device_register_stale_after_maintenance",
                    f"Maintenance says updated to {match.group(2)} on {m.date.date()}; register says {registered.iloc[0]}")

    return pd.DataFrame(findings, columns=["device_id", "severity", "flag", "evidence"])


def gateway_metrics(status: pd.DataFrame, telemetry: pd.DataFrame) -> pd.DataFrame:
    """Compare gateway heartbeat/local counts with detailed gateway receptions."""
    hourly_rows = (telemetry.assign(hour=telemetry.timestamp.dt.floor("h"))
                   .groupby(["gateway_id", "hour"]).size().rename("detail_rows").reset_index())
    joined = status.merge(hourly_rows, left_on=["gateway_id", "timestamp"],
                          right_on=["gateway_id", "hour"], how="left")
    joined["detail_rows"] = joined.detail_rows.fillna(0)
    output = []
    for gateway_id, group in joined.groupby("gateway_id"):
        offline = int(group.status.eq("offline").sum())
        backhaul_down = int(group.backhaul.eq("disconnected").sum())
        lost_est = int((group.loc[group.backhaul.eq("disconnected"), "messages_received"] -
                        group.loc[group.backhaul.eq("disconnected"), "detail_rows"]).clip(lower=0).sum())
        output.append({
            "gateway_id": gateway_id,
            "hours_observed": len(group),
            "offline_hours": offline,
            "backhaul_disconnected_hours": backhaul_down,
            "min_battery_v": pd.to_numeric(group.battery_v, errors="coerce").min(),
            "median_battery_v": pd.to_numeric(group.battery_v, errors="coerce").median(),
            "cellular_rssi_median_dbm": safe_median(group.cellular_rssi_dbm)
                if "cellular_rssi_dbm" in group else np.nan,
            "local_messages_during_backhaul_down": int(group.loc[group.backhaul.eq("disconnected"), "messages_received"].sum()),
            "detailed_rows_during_backhaul_down": int(group.loc[group.backhaul.eq("disconnected"), "detail_rows"].sum()),
            "estimated_missing_detail_rows_during_backhaul_down": lost_est,
            "detail_to_local_count_ratio_during_outage_pct": (
                100 * group.loc[group.backhaul.eq("disconnected"), "detail_rows"].sum() /
                group.loc[group.backhaul.eq("disconnected"), "messages_received"].sum()
            ) if group.loc[group.backhaul.eq("disconnected"), "messages_received"].sum() else np.nan,
        })
    return pd.DataFrame(output).sort_values("gateway_id")


def daily_completeness(devices: pd.DataFrame, telemetry: pd.DataFrame) -> pd.DataFrame:
    """Daily unique uplink counts per device for charting and incident review."""
    unique = deduplicate_uplinks(telemetry)
    unique = unique[(unique.timestamp >= DEPLOYMENT_START) & (unique.timestamp < DEPLOYMENT_END_EXCLUSIVE)].copy()
    unique["date_utc"] = unique.timestamp.dt.strftime("%Y-%m-%d")
    observed = unique.groupby(["device_id", "date_utc"]).size().rename("unique_uplinks").reset_index()
    calendar = pd.date_range(DEPLOYMENT_START.normalize(), DEPLOYMENT_END_EXCLUSIVE.normalize() - pd.Timedelta(days=1), freq="D")
    rows = []
    for d in devices.itertuples(index=False):
        if d.device_type not in EXPECTED_MINUTES:
            continue
        expected = int(1440 / EXPECTED_MINUTES[d.device_type])
        for date in calendar:
            rows.append({"device_id": d.device_id, "date_utc": date.strftime("%Y-%m-%d"), "expected_uplinks": expected})
    base = pd.DataFrame(rows).merge(observed, on=["device_id", "date_utc"], how="left")
    base["unique_uplinks"] = base.unique_uplinks.fillna(0).astype(int)
    base["completeness_pct"] = 100 * base.unique_uplinks / base.expected_uplinks
    return base


def write_outputs(input_dir: Path, output_dir: Path) -> dict[str, object]:
    devices, telemetry, status, maintenance = read_inputs(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    unique = deduplicate_uplinks(telemetry)
    summary = device_metrics(devices, telemetry)
    anomalies = build_anomalies(summary, devices, telemetry, status, maintenance)
    gateways = gateway_metrics(status, telemetry)
    daily = daily_completeness(devices, telemetry)

    summary.to_csv(output_dir / "device_summary.csv", index=False)
    anomalies.to_csv(output_dir / "anomalies.csv", index=False)
    gateways.to_csv(output_dir / "gateway_summary.csv", index=False)
    daily.to_csv(output_dir / "daily_completeness.csv", index=False)

    report = {
        "source_rows": int(len(telemetry)),
        "unique_uplinks": int(len(unique)),
        "duplicate_gateway_receptions_removed": int(len(telemetry) - len(unique)),
        "date_start_utc": DEPLOYMENT_START.isoformat(),
        "date_end_exclusive_utc": DEPLOYMENT_END_EXCLUSIVE.isoformat(),
        "device_count": int(len(devices)),
        "gateway_count": int(devices.device_type.eq("gateway").sum()),
        "anomaly_flags": int(len(anomalies)),
        "critical_flags": int(anomalies.severity.eq("critical").sum()) if not anomalies.empty else 0,
    }
    (output_dir / "run_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    LOG.info("Wrote analysis outputs to %s", output_dir)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s: %(message)s")
    try:
        result = write_outputs(args.input_dir, args.output_dir)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
