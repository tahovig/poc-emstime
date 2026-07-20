# Project: poc-emstime

## Goal

Fourth in a series of portfolio projects supporting a career pivot from software engineering to cybersecurity engineering (first: `poc-osint`, at `~/dev-projects/tah-osint-poc`; second: `poc-logids`, at `~/dev-projects/poc-logids`; third: `poc-scada`, at `~/dev-projects/poc-scada`). To build a local machine learning model for power grid time-series data that handles sub-second timestamp formatting, handles missing steps, and extracts rolling features and an integrated application to manage the model and report findings. Ultimately, this will be a cybersecurity project to capture and analyze satellite clock data for anomalies, but initial focus should be on the model and data.

## Foundational Concepts and References

Satellite clocks solve a fundamental physics problem: electricity travels at near the speed of light, meaning a millisecond difference in data collection can obscure the true state of a power grid stretching thousands of miles.Phasor Measurement Units (PMUs): PMUs sample voltage and current waveforms up to 60 times a second. Satellite clocks inject an exact timestamp into these measurements (creating synchrophasors), allowing operators to view real-time grid stability and phase angles over vast geographic regions.Sequence of Events (SOE) Recording: When a transformer blows or a circuit breaker trips, automated protective relays generate logs. A single, unified satellite time standard allows the EMS to piece together exactly "what happened when," allowing engineers to identify the root cause of a cascading failure rather than sorting through misaligned data clocks.Traveling-Wave Fault Location: When a transmission line breaks, a high-frequency electrical "wave" bounces toward both ends of the line. By using satellite clocks to measure the arrival time of this wave down to the nanosecond, utilities can pinpoint the physical location of a short circuit to within a few hundred feet, speeding up repair crews.Renewable & Microgrid Integration: Unlike traditional fossil fuel plants with heavy spinning turbines that inherently stabilize grid frequency, solar panels and wind turbines use power electronic inverters. Satellite clocks help coordinate these distributed resources so they inject power perfectly in-phase with the grid's existing alternating current (AC) cycle.

https://wsts.atis.org/wp-content/uploads/2018/11/1-3_NIST_Goldstein_Time-Sync-in-Electrical-Power.pdf
https://www.naspi.org/sites/default/files/reference_documents/tstf_electric_power_system_report_pnnl_26331_march_2017_0.pdf
https://www.novatechautomation.com/news/more-precise-timekeeping-device-synchronizes-critical-utility-functions
https://www.mobatime.com/technology/time-sync-in-energy-industry/

Their role is categorized as "System Critical" (Tier 1 infrastructure dependency). The modernization of smart grids has transitioned time synchronization from a passive tracking tool into an active mechanism for split-second safety controls. The exact level of criticality varies by sub-system.

https://www.osti.gov/servlets/purl/2584455

The Ultimate Vulnerability: GPS jitter and spoofing. Because the grid is so dependent on satellite clocks, they represent a significant vulnerability. A brief loss of a GPS signal due to weather, solar flares, jamming, or malicious cyber-spoofing can immediately desynchronize substation equipment. To mitigate this, modern substations do not rely on satellite signals alone. They use GNSS-Disciplined Oscillators (GNSSDO) or local rubidium atomic clocks to act as an internal backup, allowing the substation to safely "hold over" the precise time for hours or days even if the satellite connection drops.

https://www.pnnl.gov/sites/default/files/media/file/EED_3603_FLYER_ComplimentaryTiming_FINAL.pdf
https://www.gpsworld.com/timing-matters-the-critical-role-of-gnss-resilient-systems-in-modern-infrastructure/

Once a satellite clock establishes the time, it must be distributed to substation devices using one of three core protocols:

1. IEEE 1588 PTP (Precision Time Protocol)How it works: An Ethernet-based protocol that achieves sub-microsecond synchronization by injecting hardware-level timestamps into network packets.Power Profile (IEEE C37.238): A specific standard optimized for power utilities to account for network switch delays and prevent time degradation.Pros: Uses standard fiber/copper Ethernet cables; incredibly precise.

2. IRIG-B (Inter-Range Instrumentation Group - Code B)How it works: A legacy legacy-serial protocol that broadcasts a continuous stream of 100 pulses per second containing time and date information.Implementation: Requires dedicated, shielded coaxial or twisted-pair wiring independent of the substation network.Pros: Highly accurate and immune to network traffic congestion; requires no software overhead.

3. NTP (Network Time Protocol)How it works: A software-level network protocol operating over standard IT/OT IP networks.Precision: Millisecond-level accuracy (1 to 50ms).Pros: Ubiquitous and easy to deploy; only used for SCADA logs and human-machine interfaces where sub-microsecond precision is unnecessary.

https://www.electroind.com/synchrophasors-explained/

## Public Datasets for Time and Grid Analysis

The following public repositories provide downloadable resources:

Grid Event Signature Library (GESL): Hosted by Oak Ridge National Laboratory, this repository contains years of real-world US utility synchrophasor data. It features specific labeled examples of data artifacts caused by GPS clock errors and signal losses, making it ideal for anomaly detection.

Texas A&M Synthetic PMU Data: Provides realistic, multi-scale time-series datasets that simulate physical-law-constrained measurements. It allows you to analyze grid parameters without dealing with sensitive, non-disclosure-restricted utility infrastructure data.

Global Power-Grid Frequency Database: A massive, 26 GB repository hosting open-access power grid frequency recordings across Europe, the US, and Japan. It compiles Transmission System Operator (TSO) recordings alongside independent high-resolution measurements: https://power-grid-frequency.org/.

LBNL Open µPMU Dataset: Published by the Lawrence Berkeley National Laboratory, this dataset provides 120 Hz time-synchronized micro-phasor data collected from distribution networks, perfect for microgrid and localized phase-angle analysis: https://gridintegration.lbl.gov/publications/open-pmu-event-dataset-detection-and

## Working preferences (carried over from `poc-osint`/`poc-logids`)

- User prefers concise, direct communication — minimal explanation, no unnecessary verbosity.
- User is comfortable with CLI workflows.
- User wants critical, fact-checked pushback grounded in analysis/logic, not agreement-seeking or validation — verify claims (including your own) rather than assuming they hold.
- User values terminal/ASCII visualizations for tool output where applicable.
- User prefers to be asked before scope/data-source/cost decisions, but is fine with reversible technical implementation choices being made and stated directly rather than asked each time.