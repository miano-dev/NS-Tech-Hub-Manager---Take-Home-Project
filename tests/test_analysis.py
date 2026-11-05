import pandas as pd
import pytest

from src.analyze import (
    deduplicate_uplinks,
    device_metrics,
    expected_interval_minutes,
    expected_message_count,
    gateway_metrics,
)


def test_deduplicate_counts_one_uplink_even_if_two_gateways_hear_it():
    frame = pd.DataFrame([
        {"timestamp": "2026-03-02T00:00:00Z", "device_id": "SM-01", "gateway_id": "GW-01", "message_counter": 7},
        {"timestamp": "2026-03-02T00:00:01Z", "device_id": "SM-01", "gateway_id": "GW-02", "message_counter": 7},
        {"timestamp": "2026-03-02T00:15:00Z", "device_id": "SM-01", "gateway_id": "GW-01", "message_counter": 8},
        {"timestamp": "2026-03-02T00:00:00Z", "device_id": "SM-02", "gateway_id": "GW-01", "message_counter": 7},
    ])
    frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
    unique = deduplicate_uplinks(frame)
    assert len(unique) == 3
    assert unique["device_id"].value_counts().to_dict() == {"SM-01": 2, "SM-02": 1}


def test_expected_intervals_match_assignment():
    assert expected_interval_minutes("soil_moisture") == 15
    assert expected_interval_minutes("weather") == 15
    assert expected_interval_minutes("water_level") == 15
    assert expected_interval_minutes("gps_collar") == 60
    with pytest.raises(ValueError):
        expected_interval_minutes("unknown")


def test_six_week_expected_counts():
    assert expected_message_count("soil_moisture") == 4032
    assert expected_message_count("gps_collar") == 1008


def test_gateway_metrics_exposes_backhaul_gap_between_local_and_detail_counts():
    status = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-03-19T08:00:00Z"), "gateway_id": "GW-02",
         "status": "online", "backhaul": "disconnected", "battery_v": 13.5,
         "cellular_rssi_dbm": None, "messages_received": 34},
    ])
    telemetry = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-03-19T08:00:01Z"), "gateway_id": "GW-02"},
        {"timestamp": pd.Timestamp("2026-03-19T08:00:10Z"), "gateway_id": "GW-02"},
    ])
    result = gateway_metrics(status, telemetry).iloc[0]
    assert result["local_messages_during_backhaul_down"] == 34
    assert result["detailed_rows_during_backhaul_down"] == 2
    assert result["estimated_missing_detail_rows_during_backhaul_down"] == 32


def test_device_metrics_reports_first_invalid_gps_and_recent_solar():
    devices = pd.DataFrame([{
        "device_id": "C-TEST", "device_type": "gps_collar", "model": "test",
        "firmware_version": "1.0", "expected_gateway": "GW-01",
    }])
    telemetry = pd.DataFrame([
        {"timestamp": "2026-03-02T00:00:00Z", "device_id": "C-TEST", "gateway_id": "GW-01",
         "message_counter": 1, "battery_v": 4.1, "solar_current_ma": 1.0,
         "rssi_dbm": -100, "snr_db": 5, "latitude": 0, "longitude": 0},
        {"timestamp": "2026-04-01T00:00:00Z", "device_id": "C-TEST", "gateway_id": "GW-01",
         "message_counter": 2, "battery_v": 4.0, "solar_current_ma": 0.2,
         "rssi_dbm": -101, "snr_db": 4, "latitude": -0.5, "longitude": 36.0},
    ])
    telemetry["timestamp"] = pd.to_datetime(telemetry.timestamp, utc=True)
    result = device_metrics(devices, telemetry).iloc[0]
    assert result["gps_zero_pair_rows"] == 1
    assert result["first_gps_zero_timestamp_utc"].startswith("2026-03-02T00:00:00")
    assert result["solar_median_recent_15d_ma"] == pytest.approx(0.2)
