import type { Messages } from "./ko";

// English — every key of the ko map, enforced by the Messages type.
export const en: Messages = {
  app_name: "WildfireGuardian",

  // tabs
  tab_home: "Home",
  tab_map: "Map",
  tab_guide: "Guide",
  tab_family: "Family",
  tab_settings: "Settings",

  // shared / states
  loading_title: "One moment, please",
  loading_sub: "Loading information",
  error_title: "Could not load information",
  error_sub: "Please check your internet connection",
  error_retry: "Try again",
  updated_label: "Updated",
  close: "Close",
  save: "Save",
  saved: "Saved",

  // read aloud
  read_aloud: "Read aloud",
  read_aloud_stop: "Stop reading",
  read_screen: "Read this screen aloud",
  read_not_supported: "Read-aloud is not available on this device",

  // home
  home_btn_safe: "View map",
  home_btn_go: "See evacuation route",

  // honesty labels
  demo_banner_fallback: "DEMO — practice mode, not a real event",
  prediction_unavailable: "No spread prediction is available right now",
  mode_label: "Data",
  mode_demo: "Practice data",
  mode_live: "Live data",

  // map
  map_my_location: "My location",
  map_location_denied:
    "Location permission was not given, so we are showing the default area (near Yeongdeok)",
  map_zoom_in: "Zoom in",
  map_zoom_out: "Zoom out",
  legend_title: "Map key",
  legend_fire: "Fire detection",
  legend_spread_1h: "Predicted spread within 1 hour",
  legend_spread_3h: "Predicted spread within 3 hours",
  legend_spread_6h: "Predicted spread within 6 hours",
  legend_pathway: "Direction the fire is heading",
  legend_shelter: "Shelter",
  legend_me: "My location",
  legend_route: "Evacuation route",
  map_route_btn: "See evacuation route",
  map_route_hide: "Hide route",
  map_route_loading: "Finding a route",
  route_no_safe_walk:
    "We could not find a safe walking route. Please call 119 right now.",
  route_outside_region: "Your location is outside the service area for now",
  dist_label: "Distance",
  walk_label: "On foot",

  // guide
  guide_title: "Guide",
  guide_empty: "There is no guidance to show right now",
  call_119: "Call 119",
  open_map_action: "View map",
  open_route_action: "See evacuation route",

  // weather / fire labels (numbers always come from the server)
  wx_wind: "Wind",
  wx_humidity: "Humidity",
  wx_temp: "Temperature",
  wx_days_since_rain: "Days without rain",
  wx_wind_toward: "The wind is blowing toward your home",
  wx_wind_not_toward: "The wind is blowing away from your home",
  fire_distance: "Distance to fire",
  fire_direction: "Direction of fire",
  fire_detections: "Detected hotspots",

  // charts
  wind_compass_title: "Wind",
  wind_toward_label: "Wind blowing toward",
  timeline_title: "Detected hotspots",
  timeline_sub: "Change over time",
  eta_bar_title: "Time until fire could arrive",
  eta_bar_sub: "This is an estimate. Reality can differ.",
  dir_n: "N",
  dir_e: "E",
  dir_s: "S",
  dir_w: "W",
  unit_min: "min",
  unit_hour: "h",
  unit_km: "km",
  unit_ms: "m/s",
  unit_c: "°C",
  unit_pct: "%",
  unit_day: "days",

  // family / Guardian Plus
  family_title: "Family",
  plus_name: "Guardian Plus",
  free_title: "Safety features are free, forever",
  free_note:
    "Danger alerts, the map, spread prediction and evacuation routes are free for everyone, forever — no account needed.",
  free_1: "Danger level alerts",
  free_2: "Fire map and spread prediction",
  free_3: "Evacuation routes and shelters",
  free_4: "Live updates",
  plus_title: "Guardian Plus adds convenience",
  plus_note: "You never need to subscribe to see anything safety-related.",
  plus_1: "Automatic updates sent to your family",
  plus_2: "Alerts also by SMS and phone call",
  plus_3: "Offline map packs",
  plus_4: "Watch several home addresses",
  fam_list_title: "My family contacts",
  fam_note:
    "Contacts are stored only on this phone. They are never sent anywhere.",
  fam_name_ph: "Name",
  fam_phone_ph: "Phone number",
  fam_add: "Add",
  fam_remove: "Remove",
  fam_call: "Call",
  fam_empty: "No contacts saved yet",
  subscribe_monthly: "Subscribe monthly",
  subscribe_yearly: "Subscribe yearly",
  billing_not_configured:
    "Subscriptions are not set up yet. Please check back soon — every safety feature stays free.",
  billing_success: "Thank you for subscribing",
  billing_cancelled: "Payment was cancelled. Safety features remain free.",
  billing_redirecting: "Taking you to the payment page",

  // settings
  settings_title: "Settings",
  set_text_size: "Text size",
  text_size_normal: "Normal",
  text_size_large: "Large",
  set_language: "Language",
  set_home: "My home location",
  home_current: "Saved location",
  home_not_set: "No location saved yet",
  use_my_location: "Use my location",
  pick_on_map: "Pick on the map",
  pick_on_map_hint: "Tap the map to set your home location",
  about_title: "About this app",
  about_body:
    "WildfireGuardian tells you, in plain words, what is happening with wildfires near your home: the danger level, a map, and evacuation routes at a glance.",
  disclaimer_title: "Please read",
  disclaimer_body:
    "This app is for reference. Always follow official emergency SMS alerts, 119 instructions and village broadcasts first. This app does not replace official warnings. Spread predictions are research calculations and can differ from reality.",
  version_label: "Version",
};
