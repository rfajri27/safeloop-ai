---
doc_code: HAZOP-U100
title: Unit 100 HAZOP worksheet, revalidation 2023
type: hazop
revision: "2023"
effective_date: 2023-11-20
asset_tags: [V-201, P-101, P-101B, FV-201, NRV-101, C-200, E-301, TV-301, PSV-201]
is_current: true
is_synthetic: true
origin: synthetic
author: SafeLoop demo team
---

> SYNTHETIC DOCUMENT. A fictional HAZOP written for the SafeLoop demonstration.

# Unit 100 HAZOP worksheet, revalidation 2023

Risk matrix: 5 x 5, score = likelihood x severity. Low 1 to 4, Medium 5 to 9, High 10 to 14, Extreme 15 to 25.

## Node 1: Reflux circuit

Design intent: return 18 to 22 m3/h of reflux from V-201 to C-200 with P-101, standby P-101B.

| Row | Deviation | Cause | Consequence | S | L | Safeguards |
| --- | --- | --- | --- | --- | --- | --- |
| HZ-N1-001 | More reflux flow | FV-201 fails open | Column flooding, off-spec product | 2 | 2 | FIC-201 loop |
| HZ-N1-002 | Reverse flow | P-101 stops with discharge valve open | Backflow into V-201 | 2 | 2 | NRV-101 |
| HZ-N1-003 | No reflux | P-101 bearing failure | Loss of reflux, V-201 pressure rise, possible PSV-201 lift | 4 | 2 | P-101B auto-start, PSV-201, PAH-201 |
| HZ-N1-004 | High pressure, column overhead | Loss of reflux or overhead cooling | PSV-201 lift to flare | 4 | 1 | PSV-201, PAH-201 |
| HZ-N1-005 | High level, V-201 | P-101 trips, drum keeps filling | Liquid carry-over to vent header | 3 | 1 | LAH-201, P-101B auto-start |

Note on HZ-N1-003: credit for the P-101B auto-start assumes FT-201 is reading live (see INC-2023-009).

## Node 2: Overhead condensing

Design intent: condense column overhead vapour in E-301; TIC-301 moves TV-301 to hold condensate temperature.

| Row | Deviation | Cause | Consequence | S | L | Safeguards |
| --- | --- | --- | --- | --- | --- | --- |
| HZ-N2-001 | High condensate temperature | Loss of E-301 cooling: warm cooling-water supply or TV-301 sticking | Vapour to V-201, pressure rise | 3 | 2 | TIC-301 loop, TAH-301 |
| HZ-N2-002 | High pressure, V-201 | Loss of condenser cooling | Over-pressure of V-201, PSV-201 lift | 5 | 1 | PSV-201, PAH-201 |
| HZ-N2-003 | Contamination of condensate | E-301 tube leak | Water in recovered solvent | 2 | 2 | CW conductivity check |

Note on HZ-N2-001: the TIC-301 loop can only protect while E-301 has spare cooling.
