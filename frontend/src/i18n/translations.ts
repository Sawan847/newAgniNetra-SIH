/**
 * Bilingual English and Hindi dictionary for AgniNetra AI Command Centre.
 */

export interface TranslationDictionary {
  [key: string]: {
    en: string;
    hi: string;
  };
}

export const translations: TranslationDictionary = {
  // Navigation
  "nav.command_centre": {
    en: "Live Command Centre",
    hi: "सक्रिय कमान केंद्र",
  },
  "nav.investigation": {
    en: "Incident Investigation",
    hi: "घटना जांच एवं विश्लेषण",
  },
  "nav.facilities": {
    en: "Industrial Facilities",
    hi: "औद्योगिक प्रतिष्ठान",
  },
  "nav.analytics": {
    en: "Historical Analytics",
    hi: "ऐतिहासिक विश्लेषिकी",
  },
  "nav.alerts": {
    en: "Alerts Centre",
    hi: "चेतावनी नियंत्रण कक्ष",
  },
  "nav.model_intelligence": {
    en: "Model Intelligence",
    hi: "मॉडल बुद्धिमत्ता",
  },
  "nav.labelling": {
    en: "Analyst Labelling",
    hi: "विशेषज्ञ सत्यापन",
  },
  "nav.system_health": {
    en: "System Health",
    hi: "प्रणाली स्थिति",
  },

  // Header & Status
  "header.badge": {
    en: "NATIONAL SATELLITE THERMAL MONITORING CENTRE",
    hi: "राष्ट्रीय उपग्रह थर्मल निगरानी केंद्र",
  },
  "header.demo_mode": {
    en: "Offline Demo Mode",
    hi: "ऑफ़लाइन डेमो मोड",
  },
  "header.live": {
    en: "Live SSE Connected",
    hi: "सक्रिय उपग्रह संपर्क स्थापित",
  },
  "header.alerts_active": {
    en: "Active Alerts",
    hi: "सक्रिय चेतावनियां",
  },

  // Severities
  "severity.critical": {
    en: "Critical",
    hi: "अति गंभीर",
  },
  "severity.high": {
    en: "High",
    hi: "उच्च",
  },
  "severity.medium": {
    en: "Medium",
    hi: "मध्यम",
  },
  "severity.low": {
    en: "Low",
    hi: "सामान्य",
  },

  // Classifications
  "class.accidental_industrial_fire": {
    en: "Accidental Industrial Fire",
    hi: "आकस्मिक औद्योगिक अग्नि",
  },
  "class.flaring_and_permitted_industrial": {
    en: "Permitted Industrial Flare",
    hi: "स्वीकृत औद्योगिक फ्लेयर",
  },
  "class.agricultural_residue": {
    en: "Agricultural Residue Burning",
    hi: "कृषि पराली दहन",
  },
  "class.coal_mine_blaze": {
    en: "Coal Mine Blaze",
    hi: "कोयला खदान अग्नि",
  },
  "class.forest_wildfire": {
    en: "Forest Wildfire",
    hi: "वनाग्नि (दावानल)",
  },
  "class.solar_panel_reflection": {
    en: "Solar Panel Reflection",
    hi: "सौर संयंत्र परावर्तन",
  },
  "class.unclassified_hotspot": {
    en: "Unclassified Hotspot",
    hi: "अवर्गीकृत हॉटस्पॉट",
  },

  // Actions
  "action.investigate": {
    en: "Investigate Incident",
    hi: "घटना की जांच करें",
  },
  "action.export_dossier": {
    en: "Export PDF Dossier",
    hi: "पीडीएफ रिपोर्ट डाउनलोड करें",
  },
  "action.acknowledge": {
    en: "Acknowledge",
    hi: "स्वीकार करें",
  },
  "action.resolve": {
    en: "Resolve Incident",
    hi: "निपटारा करें",
  },
  "action.assign": {
    en: "Assign Analyst",
    hi: "विशेषज्ञ को सौंपें",
  },
  "action.refresh": {
    en: "Refresh Feed",
    hi: "ताज़ा करें",
  },
  "action.play": {
    en: "Play Replay",
    hi: "रीप्ले चलाएं",
  },
  "action.pause": {
    en: "Pause Replay",
    hi: "रोकें",
  },
  "action.filter": {
    en: "Filter Layers",
    hi: "फ़िल्टर करें",
  },

  // Common Headings
  "heading.risk_score": {
    en: "Explainable Risk Score",
    hi: "व्याख्यात्मक जोखिम सूचकांक",
  },
  "heading.two_stage_attribution": {
    en: "Two-Stage AI Attribution",
    hi: "द्वि-चरणीय कृत्रिम बुद्धिमत्ता विश्लेषण",
  },
  "heading.sensor_telemetry": {
    en: "Sensor & Radiometric Telemetry",
    hi: "उपग्रह सेंसर माप",
  },
  "heading.spectral_indices": {
    en: "Sentinel-2 Spectral Indices",
    hi: "सेंटिनल-२ स्पेक्ट्रल सूचकांक",
  },
  "heading.historical_replay": {
    en: "Historical Chronological Replay",
    hi: "ऐतिहासिक समयक्रम रीप्ले",
  },
  "heading.spectral_comparison": {
    en: "Before / After Spectral Comparison",
    hi: "घटना पूर्व / पश्चात तुलना",
  },
};
