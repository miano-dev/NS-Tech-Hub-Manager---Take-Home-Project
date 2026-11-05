# Sensor Network Challenge: data files

Six weeks of data, **2026-03-02 to 2026-04-12**, from a small LoRaWAN field network.
The data is synthetic, built from realistic patterns. It does not describe any real
installation, and the coordinates do not match any real device.

| File | Rows | Granularity |
|---|---|---|
| `devices.csv` | 21 | One row per gateway and sensor |
| `telemetry.csv` | ~64,800 | One row per message **per receiving gateway** |
| `gateway_status.csv` | 2,016 | One row per gateway per hour |
| `maintenance_log.csv` | 13 | One row per field visit and device |

All timestamps are ISO 8601 in **UTC**. Local time on site is UTC+3 (EAT). Empty cells mean
the value does not apply or was not reported.

## devices.csv

| Column | Meaning |
|---|---|
| `device_id` | Device identifier (`GW-` gateway, `SM-` soil moisture, `WS-` weather, `WL-` water level, `C-` GPS collar) |
| `device_type` | `gateway`, `soil_moisture`, `weather`, `water_level`, `gps_collar` |
| `model`, `firmware_version` | As recorded in the register |
| `install_date` | Date the device was installed |
| `latitude`, `longitude` | Installed location (WGS84). For collars, the herd's night boma |
| `location_description` | Free text |
| `expected_gateway` | The gateway this device is expected to use |

## telemetry.csv

| Column | Unit | Meaning |
|---|---|---|
| `timestamp` | UTC | Measurement time reported in the message |
| `device_id` | | Sending device |
| `gateway_id` | | Gateway that received the message |
| `message_counter` | | Uplink frame counter. Increases by one for every message the device **sends** |
| `battery_v` | V | Device battery voltage |
| `solar_current_ma` | mA | Charging current from the device's solar panel |
| `rssi_dbm`, `snr_db` | dBm, dB | Signal strength and signal-to-noise ratio at the receiving gateway |
| `soil_moisture_pct` | % VWC | Soil moisture (soil nodes) |
| `temperature_c` | °C | Soil temperature for soil nodes, air temperature for weather stations |
| `rainfall_mm` | mm | Rain since the previous message (weather stations) |
| `water_level_cm` | cm | Water depth at the sensor (water level sensors) |
| `latitude`, `longitude` | WGS84 | Position fix (collars only) |

Soil, weather and water level sensors are meant to report every 15 minutes. Collars report
every hour.

## gateway_status.csv

| Column | Meaning |
|---|---|
| `timestamp` | Start of the hour (UTC) |
| `status` | `online` if the gateway was running during the hour, `offline` if not |
| `uptime_s` | Seconds since the gateway last booted, at the end of the hour |
| `backhaul`, `backhaul_type` | Whether the gateway could reach the network server, and how |
| `cellular_rssi_dbm` | Cellular signal at the gateway |
| `battery_v` | Gateway battery voltage (12 V system) |
| `messages_received` | LoRaWAN messages the gateway heard during the hour |

The hourly status comes from the network server, filled in from the gateway's local log
when the backhaul was down.

## maintenance_log.csv

| Column | Meaning |
|---|---|
| `date` | Date of the visit (local) |
| `device_id` | Device the note refers to |
| `action` | What the field team wrote |
