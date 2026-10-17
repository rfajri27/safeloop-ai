---
doc_code: DESC-U100
title: Unit 100 process description and asset model
type: asset_model
revision: "2"
effective_date: 2025-01-10
asset_tags: [C-200, V-201, S-101, P-101, P-101B, NRV-101, FV-201, FT-201, E-301, TV-301, TIC-301, TT-301, PT-201, LT-201, PSV-201]
is_current: true
is_synthetic: true
origin: synthetic
author: SafeLoop demo team
---

> SYNTHETIC DOCUMENT. A fictional unit written for the SafeLoop demonstration. Sensor trends in the demo are shaped on public research data (NASA IMS bearings, Tennessee Eastman Process) and relabelled to these tags.

# Unit 100: Solvent Recovery

## Overview

Unit 100 recovers solvent by distillation in column C-200. Overhead vapour is condensed in E-301 and collected in reflux drum V-201. Reflux pumps P-101 (duty) and P-101B (standby) return liquid to the column.

## Node 1: Reflux circuit

- V-201 feeds both P-101 and P-101B (links L-101, L-102).
- Both pumps draw through the common suction strainer S-101 (links L-103 and L-104).
- The pumps discharge through check valve NRV-101 and flow control valve FV-201 to C-200 (links L-105 to L-108).
- FT-201 measures reflux flow (link L-109) and triggers the P-101B auto-start.
- P-101B is the standby for P-101 (link L-110).
- PSV-201 protects V-201 (link L-116). PT-201 and LT-201 measure drum pressure and level (links L-117, L-118).

## Node 2: Overhead condensing

- C-200 overhead vapour feeds E-301, which feeds V-201 (links L-111, L-112).
- TIC-301 moves cooling-water valve TV-301 to hold condensate temperature (links L-113, L-114).
- TT-301 measures condensate temperature (link L-115).

## Normal operating values

| Tag | Normal | Alarm |
| --- | --- | --- |
| FI201_REFLUX_FLOW | 18 to 22 m3/h | below 18 or above 22 |
| PI201_V201_PRESS | about 1.8 barg | PAH-201 at 2.3 barg |
| LI201_V201_LEVEL | about 50% | LAH-201 at 75% |
| TI301_CW_OUT | 32 to 38 degC | above 40 degC |
| TV301_POS | about 55% open | above 80% open |
| P101_DE_VIB_RMS | up to 2.8 mm/s | 4.5 mm/s (3.5 mm/s when tightened) |
