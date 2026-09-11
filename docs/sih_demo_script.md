# SIH26162 - five-minute demonstration

Use the actual application and dated data. Do not introduce unsupported accuracy numbers or call this an official NTRO deployment.

1. **Problem (30 seconds).** Explain that FIRMS reports thermal anomalies. Industrial heat, controlled flaring, vegetation fires and accidents can look similar; contextual evidence and temporal behavior are needed.
2. **Observed map (90 seconds).** Open `/`, choose **Explore NASA + OSM snapshot**. Show the displayed acquisition dates, 2,782 detections and 10 mapped OSM facilities. Zoom around Jamnagar, click a detection, then compare heatmap and clustering. All snapshot detections remain unclassified. Cyan facility markers establish mapped infrastructure, not accident confirmation. Use Timeline Replay to show acquisition order, not physical fire spread.
3. **Integration (60 seconds).** In System Health show OSM regional import, NASA CSV import and the FIRMS API form. The CSV works without a MAP_KEY; the Area API needs one. Explain that the database is needed for saved enrichment. Earth Engine configuration enables WorldCover and cloud-masked pre-event Sentinel-2 sampling. Missing observations remain unavailable.
4. **Review workflow (60 seconds).** If the full database is running, open an imported observation, compute features and inspect provenance. Show persistence days, facility distance/containment and imagery availability. With no reviewed-data model, show the uncertain result. Save analyst feedback with an independent evidence reference. Review alerts are a local queue; they do not dispatch emergency services.
5. **AI validation (60 seconds).** Open Model Intelligence. Explain why it currently says Not evaluated. Show the five-class training command and spatial/temporal validation protocol in the README. Present independently verified labels and evaluation as remaining work, not completed accuracy.

For a demo with just the frontend, demonstrate steps 1-2 and show the implemented workflow in the readiness guide. Do not click disabled database actions and imply an export or enrichment occurred.

## Questions to prepare for

- **What makes the system AI-based?** The supervised two-stage classifier, feature extraction and review-to-training workflow are implemented; an independently validated incident model remains to be trained.
- **How do you identify a persistent source?** Repeated prior detection days and facility context are model inputs. Repeated passes are not independent days; a seven-day snapshot is not a long-term operating baseline.
- **How do you measure success?** Held-out incident precision/recall, macro-F1, false alerts per facility/day, abstention coverage, calibration, and evaluation on unseen regions. Current software tests do not establish these metrics.
- **What cannot it detect reliably?** A hot pixel cannot confirm an accident, gas leak or explosion. Absence of a detection does not establish safety.
