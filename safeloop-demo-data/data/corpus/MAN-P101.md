---
doc_code: MAN-P101
title: P-101 / P-101B reflux pump operating and maintenance manual
type: manual
revision: "3"
effective_date: 2024-03-01
asset_tags: [P-101, P-101B, S-101]
is_current: true
is_synthetic: true
origin: synthetic
author: SafeLoop demo team
---

> SYNTHETIC DOCUMENT. Written for the SafeLoop demonstration. Not a real vendor manual.

# P-101 / P-101B reflux pump manual

## 1. Description

P-101 and P-101B are identical horizontal, single-stage centrifugal pumps. They take suction from reflux drum V-201 through one common suction strainer, S-101, and discharge through check valve NRV-101 and flow control valve FV-201 to column C-200. Rated duty is 20 m3/h. One pump runs; the other is on standby.

## 4.1 Standby operation and auto-start

P-101B starts automatically when reflux flow on FT-201 falls below 15 m3/h for 5 seconds while P-101 is selected as duty pump. The auto-start depends on FT-201 reading live. A frozen or failed FT-201 reading blocks the auto-start.

The auto-start must be tested monthly. The test includes a check that FT-201 responds to a real flow change.

## 5. Suction strainer S-101

Both pumps draw through S-101. A blocked strainer starves both pumps at the same time, so the standby pump gives no protection against strainer blockage. Check the strainer differential pressure on its local gauge every shift. Clean the strainer when the reading exceeds 0.5 bar.

## 6.1 Lubrication

Bearings are oil-bath lubricated. Change the oil every 4,000 running hours, or sooner if the oil is cloudy or a water check is positive. Water in the oil is the most common cause of early bearing failure on this pump.

## 6.3 Bearing lubrication and vibration limits

Drive-end vibration is measured as RMS velocity on tag P101_DE_VIB_RMS.

| Zone | Vibration (mm/s RMS) | Meaning |
| --- | --- | --- |
| A | up to 2.8 | Normal running |
| B | 2.8 to 4.5 | Acceptable for continuous running |
| C | 4.5 to 7.1 | Alert. Plan an inspection and an oil check within 7 days |
| D | above 7.1 | Danger. Switch to the standby pump and take P-101 out of service for inspection |

An outer-race defect usually shows as a steady rise in broadband vibration over days to weeks, often with a temporary fall before the final rise. A temporary fall does not mean the bearing has recovered.

## 6.4 Bearing temperature

Normal drive-end bearing temperature is 55 to 65 degC (tag P101_BRG_TEMP). A rise of more than 10 degC above the running baseline, or any reading above 72 degC, indicates lubrication breakdown or bearing distress.

## 7. Troubleshooting

| Symptom | Likely cause | Action |
| --- | --- | --- |
| Rising vibration and rising bearing temperature together | Bearing wear or poor lubrication | Oil sample, vibration spectrum, plan bearing change |
| Low flow on both pumps | S-101 blocked, low V-201 level | Check strainer differential pressure and drum level |
| Pump runs backwards after stopping | NRV-101 passing | Close the discharge valve, raise a work order for NRV-101 |
