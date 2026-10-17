# Data sources and licences

SafeLoop's demo plant, Unit 100, is fictional. Its sensor signals are real measurements from two public research datasets, relabelled onto Unit 100 tags. Everything else (asset model, HAZOP register, documents, golden sets, users) is synthetic and labelled `is_synthetic: true` or `origin: synthetic`.

## Public datasets

| Dataset | What we use | Licence / terms | Original source | Mirror used (pinned commit) |
| --- | --- | --- | --- | --- |
| NASA IMS Bearings, test 2 | Raw vibration snapshots, 12 to 19 Feb 2004, 4 bearings at 2,000 rpm under 6,000 lb radial load; bearing 1 failed with an outer-race defect | U.S. Government work ([usa.gov/government-works](https://www.usa.gov/government-works)), public access | [catalog.data.gov/dataset/ims-bearings](https://catalog.data.gov/dataset/ims-bearings) (NASA Prognostics Center of Excellence; data from the Center for Intelligent Maintenance Systems, University of Cincinnati) | [BLarzalere/LSTM-Autoencoder-for-Anomaly-Detection](https://github.com/BLarzalere/LSTM-Autoencoder-for-Anomaly-Detection) `db20db37`, `Sensor Data/Bearing_Sensor_Data_pt1.zip` and `pt2.zip` |
| Tennessee Eastman Process (Braatz test runs) | `d00_te.dat` (normal operation) and `d05_te.dat` (IDV 5, condenser cooling-water inlet temperature step at sample 160) | University of Illinois permissive licence; keep the copyright notice and cite the references below. Full text in `LICENSES/TEP-Braatz-UIUC-LICENSE.txt` | Large Scale Systems Research Laboratory, Prof. Richard Braatz, University of Illinois | [camaramm/tennessee-eastman-profBraatz](https://github.com/camaramm/tennessee-eastman-profBraatz) `06433188` |

**Raw data is not redistributed.** The package ships derived values only: per-snapshot statistics (`data/replay/source_features/ims_test2_features.csv`) and the hourly replay files. `tools/fetch_sources.sh` downloads the raw files; `tools/build_all.sh` rebuilds every generated file, byte for byte.

## Required citations

NASA IMS bearings:
- J. Lee, H. Qiu, G. Yu, J. Lin and Rexnord Technical Services, "Bearing Data Set", IMS, University of Cincinnati. NASA Prognostics Data Repository, NASA Ames Research Center.

Tennessee Eastman Process (as the licence asks):
- J.J. Downs and E.F. Vogel, "A plant-wide industrial process control problem", *Computers and Chemical Engineering*, 17:245-255, 1993. doi:10.1016/0098-1354(93)80018-I
- L.H. Chiang, E.L. Russell and R.D. Braatz, *Fault Detection and Diagnosis in Industrial Systems*, Springer-Verlag, London, 2001. doi:10.1007/978-1-4471-0347-9
- E.L. Russell, L.H. Chiang and R.D. Braatz, *Data-driven Techniques for Fault Detection and Diagnosis in Chemical Processes*, Springer-Verlag, London, 2000. doi:10.1007/978-1-4471-0409-4

## How each Unit 100 tag is made

`data/replay/tag_mapping.json` holds the exact transform for every tag. In short:

| Tag | Source signal | Transform | Label |
| --- | --- | --- | --- |
| `P101_DE_VIB_RMS` | IMS bearing 1, RMS of each 1 s snapshot | Mean of about 4.1 snapshots (41 min) per replay hour; scaled so the healthy median reads 2.8 mm/s | public_proxy |
| `P101_DE_VIB_KURT` | IMS bearing 1, kurtosis | Hourly mean, unscaled | public_proxy |
| `P101B_DE_VIB_RMS` | IMS bearing 4 (did not fail), RMS | Healthy first 100 hours, repeated; scaled to 2.0 mm/s | public_proxy |
| `P101_BRG_TEMP` | None: IMS has no temperature channel | First-order model driven by the real vibration, fixed noise seed | **synthetic** |
| `FI201_REFLUX_FLOW` | TEP XMEAS(14) separator underflow | 20 + (x − normal mean) × 0.8 | public_proxy |
| `LI201_V201_LEVEL` | TEP XMEAS(12) separator level | 50 + (x − normal mean) | public_proxy |
| `PI201_V201_PRESS` | TEP XMEAS(13) separator pressure, kPa | 1.80 + (x − normal mean) × 0.01 | public_proxy |
| `TI301_CW_OUT` | TEP XMEAS(22) separator cooling-water outlet | 35 + (x − normal mean) × 2 | public_proxy |
| `TV301_POS` | TEP XMV(11) condenser cooling-water flow | 55 + (x − normal mean) × 4 | public_proxy |

The rescales keep the shape and timing of the real signals but change units and ranges to fit a solvent recovery unit. They are proxies: IMS is a test rig, not a process pump, and TEP is a reactor-separator process, not a distillation column. Say so in the demo; the UI's PROXY badges do.

## Choices made from the data

- **IDV(5) instead of IDV(15) for S2.** IDV(15), condenser cooling-water valve sticking, shows no clear signal: no variable moves more than about 4 standard deviations from normal. IDV(5) shifts the condenser cooling-water valve from 18.2% to 20.8% open and holds it there.
- **24-hour recovery hold.** IMS test 2 shows the well-known temporary fall in vibration before final failure. Without a hold, P-101 would go Degraded, back to Healthy, then Degraded again.
- **P-101B uses healthy data only.** All four IMS bearings share one shaft, so the failing bearing shakes the others near the end. A separate standby pump would not.
- **Two snapshots dropped.** The last two IMS snapshots were taken after the rig stopped (RMS near zero).
