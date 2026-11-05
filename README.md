\# Natural State — Tech Hub Manager Take-Home Project



This repository contains my submission for the Natural State Tech Hub Manager take-home assignment. It includes the supplied synthetic dataset, reproducible Python analysis, automated tests, generated outputs and the two requested Markdown deliverables.



I ran the analysis and test suite locally on my PC and checked the reported figures against the generated outputs.



\## Deliverables



The two primary assignment deliverables are:



\- \*\*`deliverables/01\_sensor\_network\_analysis.md`\*\* — An evidence-based diagnosis of the six-week sensor network dataset, covering device-level and network-level performance, daily alert rules, a one-day field investigation plan and metadata ownership.

\- \*\*`deliverables/02\_deployment\_design.md`\*\* — A proposed deployment design for Laikipia, covering reporting intervals, gateway placement and backhaul, solar power sizing, software architecture, budget estimates, operational risks and the field technician model.



Supporting analysis outputs are available in `outputs/`. These CSV and JSON files are generated from the supplied synthetic dataset.



\## Repository Structure



```text

.

├── .github/

│   └── workflows/

│       └── tests.yml

├── data/

│   └── raw/                  # Supplied synthetic assignment dataset

├── deliverables/             # Two requested Markdown deliverables

├── outputs/                  # Generated analysis results

├── ai-conversations/         # AI-use transcript/share-link evidence

├── src/

│   └── analyze.py            # Reproducible pandas analysis

├── tests/

│   └── test\_analysis.py      # Automated regression tests

├── requirements.txt

└── pyproject.toml

```



\## Reproducing the Analysis



Run the following commands from the repository root.



\### 1. Install dependencies



```bash

pip install -r requirements.txt

```



\### 2. Run the analysis



```bash

python src/analyze.py --input-dir data/raw --output-dir outputs

```



The script reads the four source CSV files, performs the analysis and writes the generated results to `outputs/`.



\### 3. Run the tests



```bash

pytest

```



The test suite checks key analysis behaviours, including uplink deduplication, expected reporting intervals, six-week message counts, gateway backhaul accounting, GPS validation and recent solar-current calculations.



\## Analysis Methodology



The raw telemetry export contains gateway reception records. A single device transmission may be received by more than one gateway, so a gateway reception must not automatically be counted as a separate sensor transmission.



The analysis therefore maintains two distinct views of the data:



1\. \*\*Raw gateway receptions\*\*, retained for gateway-level RF and reception-path comparisons.

2\. \*\*Deduplicated uplink events\*\*, used for device reporting counts, reporting intervals and completeness calculations.



For the supplied six-week dataset, deduplication using `(device\_id, message\_counter)` reduces 64,773 raw reception rows to 47,035 unique uplink events.



The reporting calculations use the assignment's six-week observation window, from 2 March 2026 to 13 April 2026, with the end timestamp excluded.



The analysis also examines:



\- Expected versus observed device reporting frequency.

\- Device reporting completeness and communication gaps.

\- Gateway status, local message counters and detailed reception records.

\- Battery voltage and solar charging current.

\- Sensor-value sentinel conditions.

\- GPS `(0, 0)` coordinate pairs.

\- Rainfall flatline indicators.

\- Gateway reception distribution and RSSI/SNR measurements.

\- Firmware register inconsistencies and maintenance records.



The generated anomaly flags are transparent, rule-based indicators intended to guide investigation. They are not autonomous fault diagnoses. The written analysis distinguishes observed evidence from likely explanations and identifies additional checks where the available dataset cannot establish the physical cause.



\## Data Provenance and Limitations



The input dataset and its description were supplied as part of the assignment. 



The deduplication method assumes that device message counters do not wrap or reset within the six-week exercise window. A production LoRaWAN implementation should use a session-aware identity, incorporating the device identity, session or reset identity and uplink frame counter, to avoid incorrectly collapsing genuine transmissions.



Gateway backhaul comparisons are estimates based on the available gateway status counters and detailed telemetry records. Their interpretation depends on the counter definitions, reporting intervals and timestamp alignment. These assumptions should be confirmed against the actual gateway implementation before using the estimates as definitive packet-loss measurements.



The deployment document's equipment and infrastructure prices are planning estimates informed by publicly available supplier information. They are not formal supplier quotations or confirmed landed procurement prices for Kenya. Final costs would require supplier confirmation, shipping, taxes, installation and other applicable procurement expenses.



Radio configuration and equipment approval considerations are informed by the Communications Authority of Kenya. Final deployment must use the applicable authorised frequency plan, comply with transmit-power and equipment requirements, and confirm regulatory approval before installation.



The proposed gateway locations, coverage assumptions, solar sizing and operating arrangements are design recommendations that require field validation. In particular, terrain shadowing, collar-height radio performance, seasonal vegetation, solar availability, backhaul connectivity and site accessibility should be confirmed through a site survey and pilot deployment.



\## Use of AI-Assisted Tools



AI-assisted tools were used as part of the research, drafting, coding support (coding was done part manually) and review process. The analysis remains reproducible through the supplied Python script and test suite.



Further details and supporting evidence are provided in  the `ai-conversations/` directory.



\## Submission Notes



The repository is organised to make the submission, supporting evidence, analysis code, tests and generated results independently accessible.



The two files in `deliverables/` are the primary written responses to the assignment. The remaining repository contents provide supporting evidence and allow the analysis to be reproduced and reviewed.

