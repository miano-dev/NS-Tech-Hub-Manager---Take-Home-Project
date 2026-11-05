# Laikipia conservancy: proposed field-network design

## 1\. Monitoring devices and reporting



|Monitoring|Proposed equipment|Sampling and uplink|Rationale|
|-|-|-|-|
|12 soil plots|Calibrated soil-moisture/temperature probes with LoRaWAN node; rugged, replaceable probe and protected enclosure<br /><br />Source=https://store.nerokas.co.ke/SKU-3444<br />LSE01 uses a 4000mA Li-SOCI2 battery, It is designed for long term use up to 10 years.|Sample every 15 minutes; uplink every 30 minutes with sequence number and min/max/mean or two samples|30-minute delivery leaves margin inside the one-hour requirement while halving uplink airtime versus 15-minute transmissions. Retain raw readings locally until acknowledged.|
|3 weather sites|Research-grade station with rain gauge, temperature/humidity, wind and solar radiation, connected to a LoRaWAN encoder<br /><br />Source = Dragino<br /><br />Ultra-Low power consumption comes with 1000mAh Rechargeable Lion Battery.|Sample every 5 minutes; uplink every 15 minutes; send event-driven rainfall totals in addition to periodic summaries|Rain and wind can change quickly; the shorter interval supports event detection while using small payloads.|
|2 river points|IP-rated pressure transducer or non-contact level sensor, with a LoRaWAN node and locally stored readings<br />Source = https://www.hardwario.store/p/milesight-em410-rdl<br /><br />Milesight EM410-RDL-868M |Sample every 5 minutes; uplink every 15 minutes and on configurable rapid-level changes|A 15-minute interval gives useful flood-response resolution and still reaches the platform within an hour. Install above expected flood/debris level with a protected reference point.|
|20 cattle|Rugged GNSS collar with LoRaWAN radio, internal storage, movement detection and replaceable/solar-assisted power<br />source=https://copernitech.com/pages/products/collars.php<br /><br />Battery can last for 2 years<br /><br />**Features<br /><br />**-GNSS positioning.<br />-LoRaWAN communication.<br />-Accelerometer and gyroscope for movement monitoring.<br />-Storage of location data during connectivity interruptions.<br />-Rugged waterproof housing.<br /><br />|GNSS fix every 15 minutes while moving; transmit every 30 minutes; hourly heartbeat when stationary. Buffer position history if RF is absent.|30-minute moving reports balance grazing visibility, battery life and airtime. The collar must store fixes while outside coverage and upload them later.|

Aggregate readings where possible without discarding event peaks. Avoid confirmed uplinks for every routine sample; use confirmed downlinks sparingly because LoRaWAN downlink capacity is limited. 

Use adaptive data rate only when the surveyed link is stable. A 30-minute moving collar interval gives about 40 collar uplinks/hour, while fixed nodes add roughly 44/hour at the proposed settings; this is modest in message count, but channel airtime, spreading factor, payload size, retransmissions and local duty-cycle limits must be checked in a capacity model.

## 2\. Gateways, placement and backhaul

How I would install two outdoor, multi-channel LoRaWAN gateways: 

**Gateway A** on the northern rocky ridge at the best elevated point with confirmed 4G service.

**Gateway B** on a surveyed central/southern high point to cover valley plots, river points and the southern grazing routes. 

I would use 10-15 m masts where permitted, outdoor-rated antennas, lightning protection, proper earthing and sealed power enclosures. The gateways should overlap sufficiently for diversity; cattle collars should be tested along actual grazing routes.

Before fixing locations, I would conduct a drive/walk RF survey with representative collar hardware and test nodes at the valley floor, river bends, north ridge and southern boundary. This would be followed by mapping the RSSI/SNR and packet delivery in both wet and dry conditions. Moving or adding a third gateway should only be done if the survey shows persistent shadow areas; LoRaWAN end devices do not act as repeaters.

I would use LTE with an external high-gain antenna as Gateway A's primary backhaul. This is because usable 4G is reported on the ridge. Gateway B should use a directional point-to-point IP link to Gateway A/ridge if line of sight and legal approvals allow. Otherwise I would use a second LTE carrier where a reliable signal is measured. Keeping satellite as an optional backup should only be done if the one-hour service target justifies recurring cost. The 40 km distance to the Tech Hub is not a presumed private radio/fibre path. I would send encrypted traffic over the carrier Internet/VPN, with a surveyed 8 km site-to-HQ link as an alternate route to the HQ's powered Internet. It is important to use TLS and a VPN and not exposed management ports.

Both gateways must buffer telemetry locally during backhaul outages and replay it in order when the link returns. Monitor queue depth and oldest queued timestamp. The one-hour requirement means the design needs redundant backhaul or local edge ingestion, not merely a dashboard that looks current when connectivity is healthy.

## 3\. Power budget for one remote solar node

In this case, I am using a conservative 12 V load model for one fixed node (controller, probe and LoRa radio)and reporting every 15 minutes. 



|Load assumption|Calculation|Energy/day|
|-|-:|-:|
|Always-on controller and sleep load: 10 mA at 12 V|0.010 A × 12 V × 24 h|2.88 Wh|
|Probe excitation: 80 mA at 12 V for 5 s × 96 samples|0.080 A × 12 V × 5 s × 96 / 3,600|1.28 Wh|
|LoRa transmit: 120 mA at 12 V for 2 s × 96 uplinks|0.120 A × 12 V × 2 s × 96 / 3,600|0.08 Wh|
|**Raw total**||**4.24 Wh/day**|
|**Design load with 25% conversion/temperature/ageing allowance**|4.24 × 1.25|**5.3 Wh/day**|

using an assumption of four sunless days and a further 30% design reserve, usable storage required is **5.3 × 4 × 1.3 = 27.6 Wh. A 12.8 V, 6 Ah LiFePO4** battery stores 76.8 Wh nominal; at 80% usable depth of discharge it provides about **61 Wh usable**, or approximately 11.6 days at the design load. A 10 W panel at 3.5 peak-sun-hours/day and 65% system derating yields **10 × 3.5 × 0.65 = 22.8 Wh/day**, over four times the design load. In this case, I have used an MPPT controller, battery low-voltage cutoff, surge protection and a panel mount that can be cleaned and inspected. This margin is intentional for shading, dust, ageing and cloudy periods. 

## 4\. Data path and Hub software

The data would travel from the sensors to the servers at the Tech Hub and into NS Analytics using this path = **Sensor → LoRaWAN gateway → encrypted IP backhaul/VPN → ChirpStack Network Server at the Tech Hub → MQTT broker (Mosquitto) → Python 3.13 ingestion/validation service → PostgreSQL (plus PostGIS for locations and a time-series partitioning strategy) → NS Analytics API/dashboard.** 

Redis will only be used for cache/short-lived work queues, not as the system of record. Also, there will be Validation of payload schema, units, timestamps, frame counters, device registry, physical ranges and duplicates before storing.

Containers with Docker Compose will be run on the two existing Hub servers. in this case, I will Keep primary services on Server 1 and database/backup/ingestion replicas on Server 2, with monitoring and restore tests. I would also store raw payloads and decoded records for at least 12 months; take encrypted daily backups and a second off-site copy. During an internet failure, gateways and the local Hub queue data; the ingestion service backfills the data after recovery. ChirpStack documents a Docker Compose deployment and MQTT integration; production configuration must harden credentials, TLS, backups and network exposure.

## 5\. Asset records and field routines

I would maintain a device registry with DevEUI, serial/model, firmware, decoder, location/elevation, installation photographs, expected gateways, reporting interval, payload schema, valid ranges/sentinel values, battery chemistry, panel rating, calibration, owner, warranty and maintenance/RMA history. I would also use a controlled change log and record technician, date, old/new configuration and verification result. For the conservancy field staff, I would train them to check enclosure integrity, animal damage, panel cleanliness/shading, battery/charge voltage, antenna/cable/earth, probe seating, gauge blockage and collar fit. This would include training them to compare readings with a handheld reference and make photograph logs for changes.

## 6\. Equipment budget and risks

Planning-level USD allowances, excluding import duty, VAT, freight and final installation quotes:

|Equipment|Quantity|Source|Allowance|
|-|-:|-|-:|
|Outdoor 8/16-channel LoRaWAN gateways|2|https://www.pixelelectric.com/lora-module/8-channel-outdoor-lorawan-gateway-eg95-e-eu868/<br />https://store.nerokas.co.ke/SKU-3303?tag=Lora%20Gateway|$1,600-$2,200|
|Soil probes/nodes|12|https://store.nerokas.co.ke/SKU-3444<br />|$1,377-$1,582.20|
|Weather stations plus LoRaWAN interface|3|Dragino Kit|$2,100–$2,400|
|River-level sensors/nodes|2|https://www.hardwario.store/p/milesight-em410-rdl|$700-$840|
|GNSS LoRaWAN collars|20|suitable source=https://copernitech.com/pages/products/collars.php|$4,000-$7,000 (vendor quote required)|
|Gateway solar/battery, masts, antenna, earthing and lightning protection|2 sites|Kenyan supplier listings; installation and fabrication estimates|$2,500-$4,000|
|Optional 10 W panel/6 Ah battery/controller kits for 12 soil nodes where not included in node pricing|12|Nerokas, Pixel electric, Kenya solar shop|$600–$1,200,|
|LTE routers/antennas, PTP link and optional backhaul hardware|1 set||$700-$1,000|
|Spares, installation materials, RF survey and commissioning|1 set|Scowatt Energies, PowerBuild Kenya and local technical service estimates |$1,500-$2,500|
|Hub storage/backup allowance (servers assumed existing)|1 set|Nairobi Computer Shop, MC Trading Kenya and NetGuard Solutions |$300-$700|
|**Indicative total**|||**15,377–23,422.20, before an additional overall contingency.**|

Public reference listings have been used for the planning range including a RAK outdoor gateway, soil sensor, Milesight EM500-UDL level sensor and weather station. The prices can change based on taxation and landing costs. Also, the optional soil-node solar line is only needed if the selected node does not include an adequate power package.

Main risks: Theft is one of the main risks. This can be addressed through tamper bolts, locked enclosures, discreet GPS tags, and community agreements. Another risk is elephants/livestock which can be addressed through guarded low-level nodes, sacrificial posts and strain relief. lightning and storms also presents a risk and this can be addressed through earth rods, surge arrestors, rated enclosures and elevated mounts. Another risk is dust, heat and water which can be addressed through IP-rated hardware, breathable radiation shields and scheduled cleaning. Power deficit is also another risk which is addressable through solar reserve, and battery health alerts. Also, the risk of poor coverage/backhaul can be addressed through dual gateways, survey, buffering and alternate backhaul. It is also important to Confirm frequency, channel plan, power and equipment type approval with the Communications Authority of Kenya (CAK) before purchasing. Currently, CAK guideline says equipment intended to interwork with a communications network must be type-approved before use. This can help alot in ensuring that the right equipment are installed to avoid failure risks. CAK listed 2022 SRD guideline restricts the 865-868 MHz data-network use to four 200 kHz sub-bands (865.6-865.8, 866.2-866.4, 866.8-867.0 and 867.4-867.6 MHz), with 500 mW e.r.p. maximum, adaptive power control, and duty-cycle limits of 10% for network access points and 2.5% otherwise. An EU868 product label is not evidence of Kenyan compliance. The same guideline says 2.4/5/24/60 GHz point-to-point or point-to-multipoint WAS terminals attract an annual KSh 10,000 fee per terminal/sector ([CA guideline index](https://www.ca.go.ke/sector-guidelines), [CA SRD guideline PDF](https://www.ca.go.ke/sites/default/files/2023-06/Guidelines-on-the-Use-of-Radiofrequency-Spectrum-by-Short-Range-Devices-2022.pdf)). These are critical guidelines to use when making purchase especially when importing equipment. 

## 7\. Technician organisation and supplier quality

I would assign two trained technicians where one maintains the ridge/gateway/backhaul route and the other fixed plots/river/collars, with cross-training and a weekly joint review. In this arrangement, the Tech Hub Manager owns the queue, alert triage, inventory and change control while the project lead prioritises ecological data needs. I would also use a daily dashboard/reporting, weekly preventative inspection rotation and a monthly calibration/backup review. For repeat supplier failures, I would quarantine affected lots, maintain serial-number failure rates, demand a root-cause report and corrective-action plan. I would then test replacement units in a field pilot before deployment and enforce warranty/RMA turnaround and qualify an alternative supplier. I would also not scale a device that has not passed environmental, battery, RF and payload acceptance tests.

