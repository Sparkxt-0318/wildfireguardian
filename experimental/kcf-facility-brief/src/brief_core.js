/*
 * KCF facility brief — core (validation, adapter, model, Korean rendering).
 * Fictional exercise material. No agency endorsement. No resident data.
 * Runs unchanged in Node (tests, CLI) and in the offline viewer (inlined).
 * No network access, no dependencies.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.KCFBrief = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var CORE_VERSION = 'kcf-brief-core/1.1.0';
  var PLANNER_STATUSES = ['CHECKED_ROUTE', 'MODEL_SCOPED_NO_ROUTE', 'MISSING_INPUT', 'UNRESOLVED'];
  var REQUIRED = ['schema_version', 'case_id', 'status', 'reason', 'final_unload_s', 'groups_total',
    'people_total', 'people_with_checked_transport', 'trips', 'missing_information', 'assumptions'];
  var VEHICLE_STATUSES = ['READY', 'EN_ROUTE', 'DELAYED', 'UNAVAILABLE', 'UNKNOWN'];
  var DEST_STATUSES = ['CONFIRMED', 'AWAITING_CONFIRMATION', 'UNKNOWN'];

  var STATUS_KO = {
    CHECKED_ROUTE: '경로 계산 확인 (모델 범위 안)',
    MODEL_SCOPED_NO_ROUTE: '모델 범위 안에서 경로 없음',
    MISSING_INPUT: '입력 자료 결측 — 판정 불가',
    UNRESOLVED: '미해결'
  };
  var VEHICLE_KO = { READY: '대기', EN_ROUTE: '이동 중', DELAYED: '지연', UNAVAILABLE: '사용 불가', UNKNOWN: '확인 안 됨' };
  var DEST_KO = { CONFIRMED: '수용 확인', AWAITING_CONFIRMATION: '수용 확인 대기', UNKNOWN: '미확인' };
  var ROAD_KO = { UNKNOWN: '통제 여부 모름', CLOSED_REPORTED: '통제 보고(가상)', OPEN_REPORTED: '통행 보고(가상)' };
  var DEFAULT_ROLES = {
    facility: '시설 당직 책임자', county: '시군 재난안전 상황실', fire: '소방 구급 지원',
    police: '경찰 교통 담당', destination: '수용기관 담당자'
  };

  // Field aliases accepted from a planner whose trip naming differs slightly.
  var TRIP_ALIASES = {
    trip_id: ['trip_id', 'id', 'trip'],
    vehicle_id: ['vehicle_id', 'vehicle'],
    group_id: ['group_id', 'group'],
    people: ['people', 'people_count', 'passengers', 'n_people'],
    vehicle_status: ['vehicle_status'],
    assignment_checked: ['assignment_checked', 'checked', 'transport_checked'],
    depart_s: ['depart_s', 'departure_s', 'depart_time_s'],
    unload_s: ['unload_s', 'unload_time_s', 'arrival_unload_s', 'unloading_end_s'],
    boarding_s: ['boarding_s', 'boarding_duration_s'],
    destination_id: ['destination_id', 'destination', 'end_node'],
    destination_status: ['destination_status'],
    mobility_need: ['mobility_need', 'transport_need'],
    kind: ['kind']
  };

  // ---------- helpers ----------
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function isObj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
  function isNonNegInt(v) { return typeof v === 'number' && Number.isInteger(v) && v >= 0; }
  function isTime(v) { return v === null || (typeof v === 'number' && isFinite(v) && v >= 0); }
  function pick(obj, names) {
    for (var i = 0; i < names.length; i++) if (Object.prototype.hasOwnProperty.call(obj, names[i])) return { found: true, value: obj[names[i]], key: names[i] };
    return { found: false };
  }
  function parseClock(c) {
    if (c == null) return null;
    var m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(String(c));
    return m ? Number(m[1]) * 60 + Number(m[2]) : NaN;
  }

  // ---------- SHA-256 (pure JS so file:// pages need no secure context) ----------
  function sha256(str) {
    var bytes = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
        var c2 = str.charCodeAt(i + 1);
        if (c2 >= 0xdc00 && c2 <= 0xdfff) { c = 0x10000 + ((c - 0xd800) << 10) + (c2 - 0xdc00); i++; }
      }
      if (c < 0x80) bytes.push(c);
      else if (c < 0x800) bytes.push(0xc0 | (c >> 6), 0x80 | (c & 63));
      else if (c < 0x10000) bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
      else bytes.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    var K = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
      0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
      0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
      0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
      0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
      0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
      0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
      0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2];
    var H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
    var bitLen = bytes.length * 8;
    bytes.push(0x80);
    while (bytes.length % 64 !== 56) bytes.push(0);
    var hi = Math.floor(bitLen / 0x100000000), lo = bitLen >>> 0;
    bytes.push((hi >>> 24) & 255, (hi >>> 16) & 255, (hi >>> 8) & 255, hi & 255, (lo >>> 24) & 255, (lo >>> 16) & 255, (lo >>> 8) & 255, lo & 255);
    var W = new Array(64);
    function rotr(x, n) { return (x >>> n) | (x << (32 - n)); }
    for (var off = 0; off < bytes.length; off += 64) {
      for (var t = 0; t < 16; t++) W[t] = (bytes[off + 4 * t] << 24) | (bytes[off + 4 * t + 1] << 16) | (bytes[off + 4 * t + 2] << 8) | bytes[off + 4 * t + 3];
      for (t = 16; t < 64; t++) {
        var s0 = rotr(W[t - 15], 7) ^ rotr(W[t - 15], 18) ^ (W[t - 15] >>> 3);
        var s1 = rotr(W[t - 2], 17) ^ rotr(W[t - 2], 19) ^ (W[t - 2] >>> 10);
        W[t] = (W[t - 16] + s0 + W[t - 7] + s1) | 0;
      }
      var a = H[0], b = H[1], c3 = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (t = 0; t < 64; t++) {
        var S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        var ch = (e & f) ^ (~e & g);
        var t1 = (h + S1 + ch + K[t] + W[t]) | 0;
        var S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        var maj = (a & b) ^ (a & c3) ^ (b & c3);
        var t2 = (S0 + maj) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0; d = c3; c3 = b; b = a; a = (t1 + t2) | 0;
      }
      H[0] = (H[0] + a) | 0; H[1] = (H[1] + b) | 0; H[2] = (H[2] + c3) | 0; H[3] = (H[3] + d) | 0;
      H[4] = (H[4] + e) | 0; H[5] = (H[5] + f) | 0; H[6] = (H[6] + g) | 0; H[7] = (H[7] + h) | 0;
    }
    return H.map(function (x) { return ('00000000' + (x >>> 0).toString(16)).slice(-8); }).join('');
  }

  // ---------- personal-data guard ----------
  var PII_KEY = /^(.*_)?(name|names|full_name|phone|tel|mobile|email|contact|contacts|address|birth|birthdate|dob|rrn|ssn|patient_id|resident_id|record_no)$/i;
  var PII_KEY_KO = /(성명|이름|연락처|전화|휴대|주소|주민|생년|환자번호)/;
  var PII_VAL = [
    { re: /01[016789][- .]?\d{3,4}[- .]?\d{4}/, why: '휴대전화 번호 형식' },
    { re: /0\d{1,2}-\d{3,4}-\d{4}/, why: '전화번호 형식' },
    { re: /\d{6}-[1-4]\d{6}/, why: '주민등록번호 형식' },
    { re: /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/, why: '이메일 형식' }
  ];
  function scanPII(obj, where, errors) {
    (function walk(v, path) {
      if (Array.isArray(v)) { v.forEach(function (x, i) { walk(x, path + '[' + i + ']'); }); return; }
      if (isObj(v)) {
        Object.keys(v).forEach(function (k) {
          if (PII_KEY.test(k) || PII_KEY_KO.test(k)) errors.push(where + ': 개인정보로 보이는 필드는 받지 않음 (' + path + '.' + k + ')');
          walk(v[k], path + '.' + k);
        });
        return;
      }
      if (typeof v === 'string') {
        PII_VAL.forEach(function (p) { if (p.re.test(v)) errors.push(where + ': 개인정보로 보이는 값 (' + p.why + ') at ' + path); });
      }
    })(obj, '$');
  }

  function normItem(x, i, where, errors) {
    if (typeof x === 'string') return { code: null, kind: null, text: x, who: null };
    if (isObj(x)) {
      var text = x.text_ko || x.text || x.description || describeMissing(x);
      if (typeof text !== 'string' || !text) errors.push(where + '[' + i + ']: 설명 문구(text_ko/text) 없음');
      return { code: x.code || x.id || null, kind: x.kind || null, text: text || '', who: x.who_role || null };
    }
    errors.push(where + '[' + i + ']: 문자열 또는 객체여야 함');
    return { code: null, kind: null, text: '', who: null };
  }

  // Korean text for structured planner missing-information items that carry no text.
  function describeMissing(x) {
    if (x.kind === 'UNKNOWN_EDGE_INTERVAL' && x.edge_id != null && Array.isArray(x.unknown_interval)) {
      return '모델 입력 미확인: 도로 구간 ' + x.edge_id + ' 의 T0+' + x.unknown_interval[0] + '초~' + x.unknown_interval[1] + '초 상태 모름' +
        (x.vehicle_id ? ' (' + x.vehicle_id + (x.group_id ? '·' + x.group_id : '') + ' 운행에 필요)' : '') + ' — 모름은 안전하다는 뜻 아님';
    }
    if (typeof x.kind === 'string') {
      var rest = Object.keys(x).filter(function (k) { return k !== 'kind'; }).map(function (k) { return k + '=' + JSON.stringify(x[k]); }).join(', ');
      return '플래너 미확인 항목 ' + x.kind + (rest ? ' (' + rest + ')' : '');
    }
    return null;
  }

  // ---------- planner output: normalize + validate ----------
  function normalizePlanner(raw, label) {
    label = label || '플래너 출력';
    var errors = [], warnings = [];
    if (!isObj(raw)) return { data: null, errors: [label + ': JSON 객체가 아님'], warnings: warnings };
    REQUIRED.forEach(function (k) { if (!Object.prototype.hasOwnProperty.call(raw, k)) errors.push(label + ': 필수 필드 없음 — ' + k); });
    if (errors.length) return { data: null, errors: errors, warnings: warnings };
    scanPII(raw, label, errors);

    if (isNonNegInt(raw.schema_version)) {
      // kcf-facility-planner writes an integer schema_version (SCHEMA.md: "exactly 1").
      warnings.push(label + ': 정수 schema_version ' + raw.schema_version + ' → "' + raw.schema_version + '" 로 읽음');
      raw = Object.assign({}, raw, { schema_version: String(raw.schema_version) });
    }
    if (typeof raw.schema_version !== 'string' || !raw.schema_version) errors.push(label + ': schema_version 은 문자열 또는 0 이상 정수여야 함');
    if (raw.status === 'INVALID_INPUT') errors.push(label + ': 플래너가 INVALID_INPUT (입력 오류)을 반환함 — 사유: ' + raw.reason);
    if (typeof raw.case_id !== 'string' || !raw.case_id) errors.push(label + ': case_id 는 비어 있지 않은 문자열이어야 함');
    if (PLANNER_STATUSES.indexOf(raw.status) < 0) errors.push(label + ': 알 수 없는 status — ' + raw.status);
    if (raw.reason !== null && typeof raw.reason !== 'string') errors.push(label + ': reason 은 문자열 또는 null');
    if (!isTime(raw.final_unload_s)) errors.push(label + ': final_unload_s 는 0 이상 숫자 또는 null (모름)');
    ['groups_total', 'people_total', 'people_with_checked_transport'].forEach(function (k) {
      if (!isNonNegInt(raw[k])) errors.push(label + ': ' + k + ' 는 0 이상 정수여야 함');
    });
    ['trips', 'missing_information', 'assumptions'].forEach(function (k) {
      if (!Array.isArray(raw[k])) errors.push(label + ': ' + k + ' 는 배열이어야 함');
    });
    if (errors.length) return { data: null, errors: errors, warnings: warnings };

    // kcf-facility-planner dialect: `trips` holds checked witness trips only, listed groups in
    // groups_with_checked_transport (SCHEMA.md "Coverage"). Map that to assignment_checked.
    var witnessGroups = Array.isArray(raw.groups_with_checked_transport) ? raw.groups_with_checked_transport.map(String) : null;
    if (witnessGroups) warnings.push(label + ': kcf-facility-planner 형식 — trips 는 확인된 운행만 포함 (groups_with_checked_transport 기준으로 배정 확인 표시)');
    if (Array.isArray(raw.conditional_trips) && raw.conditional_trips.length)
      warnings.push(label + ': conditional_trips ' + raw.conditional_trips.length + '건은 미확인 구간이 열려 있어야만 가능한 일정 — 확인된 운행으로 표시하지 않음');
    var trips = raw.trips.map(function (t, i) {
      var where = label + ' trips[' + i + ']';
      if (!isObj(t)) { errors.push(where + ': 객체가 아님'); return null; }
      if (witnessGroups && !('assignment_checked' in t)) {
        t = Object.assign({}, t, { assignment_checked: t.kind !== 'empty_return' && t.group_id != null && witnessGroups.indexOf(String(t.group_id)) >= 0 });
        if (!('boarding_s' in t) && typeof t.boarding_start_s === 'number' && typeof t.boarding_end_s === 'number') t.boarding_s = t.boarding_end_s - t.boarding_start_s;
        if (t.kind === 'empty_return' && !('unloading_end_s' in t && t.unloading_end_s != null)) t.unload_s = t.arrival_s == null ? null : t.arrival_s;
      }
      var out = { _raw_keys: Object.keys(t) };
      Object.keys(TRIP_ALIASES).forEach(function (f) {
        var p = pick(t, TRIP_ALIASES[f]);
        out[f] = p.found ? p.value : undefined;
        if (p.found && p.key !== f) warnings.push(where + ': 필드 별칭 ' + p.key + ' → ' + f + ' 로 읽음');
      });
      if (out.trip_id == null) { out.trip_id = 'T' + (i + 1); warnings.push(where + ': trip_id 없음 → ' + out.trip_id + ' 부여'); }
      out.trip_id = String(out.trip_id);
      if (!isNonNegInt(out.people)) errors.push(where + ': people 는 0 이상 정수여야 함');
      ['depart_s', 'unload_s', 'boarding_s'].forEach(function (f) {
        if (out[f] === undefined) { out[f] = null; if (f !== 'boarding_s') warnings.push(where + ': ' + f + ' 없음 → 모름으로 표시'); }
        else if (!isTime(out[f])) errors.push(where + ': ' + f + ' 는 0 이상 숫자 또는 null');
      });
      if (typeof out.depart_s === 'number' && typeof out.unload_s === 'number' && out.unload_s < out.depart_s)
        errors.push(where + ': 하차 시각(' + out.unload_s + 's)이 출발 시각(' + out.depart_s + 's)보다 빠름');
      if (out.vehicle_status === undefined || out.vehicle_status === null) out.vehicle_status = 'UNKNOWN';
      else if (VEHICLE_STATUSES.indexOf(out.vehicle_status) < 0) { warnings.push(where + ': 알 수 없는 vehicle_status "' + out.vehicle_status + '" → 확인 안 됨'); out.vehicle_status = 'UNKNOWN'; }
      if (out.destination_status === undefined || out.destination_status === null) out.destination_status = 'UNKNOWN';
      else if (DEST_STATUSES.indexOf(out.destination_status) < 0) { warnings.push(where + ': 알 수 없는 destination_status → 미확인'); out.destination_status = 'UNKNOWN'; }
      if (out.assignment_checked !== undefined && typeof out.assignment_checked !== 'boolean') errors.push(where + ': assignment_checked 는 true/false');
      if (out.assignment_checked === true && out.vehicle_status === 'UNAVAILABLE') errors.push(where + ': 사용 불가 차량인데 배정 확인으로 표시됨');
      if (out.assignment_checked === true && (out.depart_s === null || out.unload_s === null) && raw.status === 'CHECKED_ROUTE')
        warnings.push(where + ': 배정 확인인데 출발/하차 시각이 모름');
      if (out.vehicle_id != null) out.vehicle_id = String(out.vehicle_id);
      if (out.group_id != null) out.group_id = String(out.group_id);
      if (out.destination_id != null) out.destination_id = String(out.destination_id);
      return out;
    });
    if (errors.length) return { data: null, errors: errors, warnings: warnings };

    var ids = {};
    trips.forEach(function (t) { if (ids[t.trip_id]) errors.push(label + ': trip_id 중복 — ' + t.trip_id); ids[t.trip_id] = 1; });

    var total = raw.people_total, checked = raw.people_with_checked_transport;
    if (checked > total) errors.push(label + ': 이송 확인 인원(' + checked + ')이 전체 인원(' + total + ')보다 많음');
    var tripSum = trips.reduce(function (s, t) { return s + t.people; }, 0);
    if (tripSum > total) errors.push(label + ': 운행별 인원 합(' + tripSum + ')이 전체 인원(' + total + ')보다 많음');
    var allFlag = trips.every(function (t) { return typeof t.assignment_checked === 'boolean'; });
    var reconciled = false;
    if (allFlag) {
      var checkedSum = trips.reduce(function (s, t) { return s + (t.assignment_checked ? t.people : 0); }, 0);
      if (checkedSum !== checked) errors.push(label + ': 배정 확인 운행 인원 합(' + checkedSum + ') ≠ people_with_checked_transport(' + checked + ')');
      else reconciled = true;
    } else if (trips.length) {
      warnings.push(label + ': 일부 운행에 assignment_checked 없음 → 운행별 인원 대조 못 함 (총계만 표시)');
    }
    var groupIds = {};
    trips.forEach(function (t) { if (t.group_id != null) groupIds[t.group_id] = 1; });
    if (Object.keys(groupIds).length > raw.groups_total) errors.push(label + ': 운행에 나온 그룹 수가 groups_total(' + raw.groups_total + ')보다 많음');

    var fu = raw.final_unload_s;
    if (fu !== null) {
      if (checked < total) errors.push(label + ': ' + (total - checked) + '명이 미확정인데 final_unload_s 가 숫자임 (지난 값이 남은 것으로 간주, 거부)');
      if (raw.status !== 'CHECKED_ROUTE') errors.push(label + ': status ' + raw.status + ' 인데 final_unload_s 가 숫자임');
      var ct = trips.filter(function (t) { return t.assignment_checked === true; });
      if (ct.some(function (t) { return t.unload_s === null; })) errors.push(label + ': 하차 시각 모르는 운행이 있는데 final_unload_s 가 숫자임');
      else if (ct.length && allFlag) {
        var mx = Math.max.apply(null, ct.map(function (t) { return t.unload_s; }));
        if (Math.abs(mx - fu) > 1) errors.push(label + ': final_unload_s(' + fu + ') ≠ 운행 하차 시각 최댓값(' + mx + ')');
      }
    }
    if (raw.status === 'CHECKED_ROUTE' && checked < total) warnings.push(label + ': CHECKED_ROUTE 이지만 ' + (total - checked) + '명 미확정');

    var mi = raw.missing_information.map(function (x, i) { return normItem(x, i, label + ' missing_information', errors); });
    var as = raw.assumptions.map(function (x, i) { return normItem(x, i, label + ' assumptions', errors); });
    if (witnessGroups && !as.some(function (x) { return x.kind === 'MODEL_FIRE_RESTRICTION'; })) {
      // The planner lists closures as plain-text rules; its fixtures describe closures as simulated fire restrictions.
      as.push({ code: 'ADAPTER_CLOSED_AS_MODEL_FIRE', kind: 'MODEL_FIRE_RESTRICTION', who: null,
        text: '플래너의 통제(closed) 구간 = 모의 화재 제한으로 읽음, 관측된 도로 통제 아님 (어댑터 해석 — 플래너 원문 가정은 아래 전제 참조)' });
      warnings.push(label + ': 화재 제한 가정에 kind 표시가 없어 어댑터 해석 문구를 추가함');
    }
    if (errors.length) return { data: null, errors: errors, warnings: warnings };

    return {
      data: {
        schema_version: raw.schema_version, case_id: raw.case_id, status: raw.status, reason: raw.reason,
        final_unload_s: fu, groups_total: raw.groups_total, people_total: total,
        people_with_checked_transport: checked, trips: trips, missing_information: mi, assumptions: as,
        reconciled: reconciled
      },
      errors: errors, warnings: warnings
    };
  }

  // ---------- briefing metadata ----------
  function defaultMeta(caseId) {
    return {
      meta_version: 'kcf-brief-meta/1', case_id: caseId, _default: true,
      exercise_label: '훈련 · 가상 상황 · 실제 상황 아님',
      facility: { label: '시설명 미제공 (가상)', short: '해당 시설' },
      time_origin: { label: 'T0 = 메타데이터 미제공 (플래너 시각 원점)', clock: null },
      roles: {}, groups: null, vehicles: {}, destinations: {},
      updates: { baseline: { at_s: null, source_label: '기준 플래너 출력' }, revised: { at_s: null, source_label: '변경 플래너 출력' } },
      field_reports: [], road_status: [], assistance_requests: []
    };
  }

  function normalizeMeta(raw, label) {
    label = label || '브리핑 메타데이터';
    var errors = [], warnings = [];
    if (!isObj(raw)) return { meta: null, errors: [label + ': JSON 객체가 아님'], warnings: warnings };
    scanPII(raw, label, errors);
    if (typeof raw.case_id !== 'string' || !raw.case_id) errors.push(label + ': case_id 없음');
    if (typeof raw.exercise_label !== 'string' || raw.exercise_label.indexOf('훈련') < 0) errors.push(label + ': exercise_label 에 "훈련" 표시가 있어야 함');
    var to = raw.time_origin;
    if (!isObj(to) || typeof to.label !== 'string' || !to.label) errors.push(label + ': time_origin.label (T0 정의) 필요');
    else if (to.clock != null && isNaN(parseClock(to.clock))) errors.push(label + ': time_origin.clock 은 HH:MM 형식');
    var up = raw.updates;
    if (!isObj(up) || !isObj(up.baseline)) errors.push(label + ': updates.baseline 필요');
    else {
      ['baseline', 'revised'].forEach(function (k) {
        if (!up[k]) return;
        if (!isTime(up[k].at_s) || up[k].at_s === undefined) errors.push(label + ': updates.' + k + '.at_s 는 0 이상 숫자 또는 null');
      });
    }
    var m = {
      meta_version: raw.meta_version || 'kcf-brief-meta/1', case_id: raw.case_id,
      exercise_label: raw.exercise_label,
      facility: isObj(raw.facility) ? raw.facility : { label: '시설명 미제공 (가상)' },
      time_origin: to || {}, roles: isObj(raw.roles) ? raw.roles : {},
      groups: Array.isArray(raw.groups) ? raw.groups : null,
      vehicles: isObj(raw.vehicles) ? raw.vehicles : {}, destinations: isObj(raw.destinations) ? raw.destinations : {},
      updates: up || {}, field_reports: Array.isArray(raw.field_reports) ? raw.field_reports : [],
      road_status: Array.isArray(raw.road_status) ? raw.road_status : [],
      assistance_requests: Array.isArray(raw.assistance_requests) ? raw.assistance_requests : [],
      facilitator_note: raw.facilitator_note || null
    };
    if (!m.facility.short) m.facility.short = m.facility.label;
    if (m.groups) {
      var seen = {};
      m.groups.forEach(function (g, i) {
        if (!isObj(g) || typeof g.group_id !== 'string') { errors.push(label + ': groups[' + i + '].group_id 필요'); return; }
        if (seen[g.group_id]) errors.push(label + ': group_id 중복 — ' + g.group_id);
        seen[g.group_id] = 1;
        if (!isNonNegInt(g.people)) errors.push(label + ': groups[' + i + '].people 는 0 이상 정수');
        if (typeof g.label !== 'string') errors.push(label + ': groups[' + i + '].label 필요');
      });
    }
    m.field_reports.forEach(function (f, i) {
      if (!isObj(f) || !isTime(f.at_s) || f.at_s === null || typeof f.text !== 'string') errors.push(label + ': field_reports[' + i + '] 는 {at_s(숫자), text} 필요');
    });
    m.road_status.forEach(function (r, i) {
      if (!isObj(r) || typeof r.segment !== 'string' || !ROAD_KO[r.status]) errors.push(label + ': road_status[' + i + '] 는 {segment, status: UNKNOWN|CLOSED_REPORTED|OPEN_REPORTED}');
    });
    return { meta: errors.length ? null : m, errors: errors, warnings: warnings };
  }

  // ---------- pair checks ----------
  function crossCheck(snap, meta, which, atS, errors, warnings) {
    var tag = which === 'baseline' ? '기준' : '변경';
    if (meta.groups) {
      var gsum = meta.groups.reduce(function (s, g) { return s + g.people; }, 0);
      var gmap = {};
      meta.groups.forEach(function (g) { gmap[g.group_id] = g; });
      if (which === 'revised' || which === 'single') {
        if (gsum !== snap.people_total) errors.push('메타 그룹 인원 합(' + gsum + ') ≠ ' + tag + ' people_total(' + snap.people_total + ')');
        if (meta.groups.length !== snap.groups_total) errors.push('메타 그룹 수(' + meta.groups.length + ') ≠ ' + tag + ' groups_total(' + snap.groups_total + ')');
      } else if (gsum !== snap.people_total) {
        warnings.push('기준 출력의 전체 인원(' + snap.people_total + ')이 메타 그룹 합(' + gsum + ')과 다름 — 인원 변동으로 표시');
      }
      var per = {};
      snap.trips.forEach(function (t) {
        if (t.group_id == null) { warnings.push(tag + ' ' + t.trip_id + ': group_id 없음'); return; }
        if (!gmap[t.group_id]) { errors.push(tag + ' ' + t.trip_id + ': 메타에 없는 그룹 ' + t.group_id); return; }
        per[t.group_id] = (per[t.group_id] || 0) + t.people;
      });
      Object.keys(per).forEach(function (gid) {
        if (gmap[gid] && per[gid] > gmap[gid].people && (which !== 'baseline' || gsum === snap.people_total))
          errors.push(tag + ': 그룹 ' + gid + ' 운행 인원(' + per[gid] + ')이 그룹 인원(' + gmap[gid].people + ')보다 많음');
      });
    }
    if (typeof atS === 'number') {
      snap.trips.forEach(function (t) {
        if (typeof t.depart_s === 'number' && t.depart_s < atS && (t.vehicle_status === 'READY' || t.vehicle_status === 'DELAYED'))
          errors.push(tag + ' ' + t.trip_id + ': 보고 시각(' + atS + 's) 이전에 출발했다는데 차량 상태가 ' + VEHICLE_KO[t.vehicle_status] + ' — 불가능한 시각');
      });
    }
  }

  function validateBrief(baselineRaw, revisedRaw, metaRaw, opts) {
    opts = opts || {};
    var errors = [], warnings = [];
    var b = normalizePlanner(baselineRaw, '기준(baseline)');
    errors = errors.concat(b.errors); warnings = warnings.concat(b.warnings);
    var r = null;
    if (revisedRaw != null) {
      r = normalizePlanner(revisedRaw, '변경(revised)');
      errors = errors.concat(r.errors); warnings = warnings.concat(r.warnings);
    }
    var meta = null;
    if (metaRaw != null) {
      var mm = normalizeMeta(metaRaw);
      errors = errors.concat(mm.errors); warnings = warnings.concat(mm.warnings);
      meta = mm.meta;
    }
    if (errors.length) return { ok: false, errors: errors, warnings: warnings };
    var B = b.data, R = r ? r.data : null;
    if (!meta) { meta = defaultMeta(B.case_id); warnings.push('메타데이터 미제공 — 그룹·역할·보고 시각은 "미제공"으로 표시'); }
    if (R && R.case_id !== B.case_id) errors.push('다른 사례끼리 비교 불가: 기준 ' + B.case_id + ' / 변경 ' + R.case_id);
    if (meta.case_id !== B.case_id) errors.push('메타 case_id(' + meta.case_id + ')가 플래너 case_id(' + B.case_id + ')와 다름');
    if (R && B.schema_version.split('.')[0] !== R.schema_version.split('.')[0]) warnings.push('schema_version 다름: ' + B.schema_version + ' / ' + R.schema_version);
    var ub = meta.updates.baseline || {}, ur = meta.updates.revised || {};
    var tb = ub.at_s == null ? null : ub.at_s, tr = ur.at_s == null ? null : ur.at_s;
    if (R && tb !== null && tr !== null && !(tr > tb)) errors.push('갱신 시각 순서 오류: 변경 보고(' + tr + 's)가 기준 보고(' + tb + 's)보다 늦어야 함');
    if (R && !meta._default && !meta.updates.revised) errors.push('메타에 updates.revised (변경 보고 시각) 없음');
    var latest = R ? tr : tb;
    if (!R && latest !== null) {
      // Single snapshot (e.g. "what the county saw before the change"): reports made after it did not exist yet.
      var before = meta.field_reports.filter(function (f) { return f.at_s <= latest; });
      if (before.length !== meta.field_reports.length) {
        meta = Object.assign({}, meta, { field_reports: before });
        warnings.push('이 보고 시각 이후에 나온 가상 현장 보고는 제외하고 표시');
      }
    }
    meta.field_reports.forEach(function (f, i) {
      if (latest !== null && f.at_s > latest) errors.push('가상 현장 보고 ' + (i + 1) + ': 보고 시각(' + f.at_s + 's)이 최신 갱신(' + latest + 's)보다 늦음');
    });
    if (errors.length) return { ok: false, errors: errors, warnings: warnings };
    crossCheck(B, meta, R ? 'baseline' : 'single', tb, errors, warnings);
    if (R) crossCheck(R, meta, 'revised', tr, errors, warnings);
    if (errors.length) return { ok: false, errors: errors, warnings: warnings };
    return { ok: true, errors: [], warnings: warnings, baseline: B, revised: R, meta: meta };
  }

  // ---------- time formatting ----------
  function minutesUp(s) { return Math.ceil(s / 60); }
  function clockOf(meta, s) {
    var c = parseClock(meta.time_origin && meta.time_origin.clock);
    if (c == null || isNaN(c) || s == null) return null;
    var m = (c + minutesUp(s)) % 1440;
    return ('0' + Math.floor(m / 60)).slice(-2) + ':' + ('0' + (m % 60)).slice(-2);
  }
  function fmtT(meta, s) {
    if (s === null || s === undefined) return '모름';
    var clk = clockOf(meta, s);
    return 'T0+' + minutesUp(s) + '분' + (clk ? ' (' + clk + ')' : '');
  }
  function spokenT(meta, s) {
    if (s == null) return null;
    var clk = clockOf(meta, s);
    if (clk) { var p = clk.split(':'); return Number(p[0]) + '시 ' + Number(p[1]) + '분'; }
    return '훈련 시작 ' + minutesUp(s) + '분 뒤';
  }
  function fmtDur(s) { return s == null ? '모름' : minutesUp(s) + '분'; }

  // ---------- model ----------
  function role(meta, k) { return (meta.roles && meta.roles[k]) || DEFAULT_ROLES[k] || k; }
  function vLabel(meta, id) { var v = meta.vehicles && meta.vehicles[id]; return v ? (v.label || id) : (id == null ? '차량 미지정' : id); }
  function vShort(meta, id) { var v = meta.vehicles && meta.vehicles[id]; return v ? (v.short || v.label || id) : (id == null ? '미지정 차량' : id); }
  function dLabel(meta, id) { var d = meta.destinations && meta.destinations[id]; return d ? (d.label || id) : (id == null ? '목적지 미정' : id); }

  function groupsFor(meta, snap) {
    if (meta.groups) return meta.groups.map(function (g) { return { group_id: g.group_id, label: g.label, people: g.people, need: g.need || '미제공', spoken: g.spoken || g.label, request: g.request || null, request_role: g.request_role || 'county' }; });
    var per = {}, order = [];
    snap.trips.forEach(function (t) { if (t.group_id == null && t.people === 0) return; var k = t.group_id || '미지정'; if (!(k in per)) { per[k] = 0; order.push(k); } per[k] += t.people; });
    var out = order.map(function (k) { return { group_id: k, label: k + ' (메타 미제공)', people: per[k], need: '미제공', spoken: k + ' 그룹', request: null, request_role: 'county', derived: true }; });
    var sum = order.reduce(function (s, k) { return s + per[k]; }, 0);
    if (sum < snap.people_total) out.push({ group_id: '미배정', label: '운행 미배정 인원', people: snap.people_total - sum, need: '미제공', spoken: '운행 미배정', request: null, request_role: 'county', derived: true });
    return out;
  }

  function summarize(snap, meta) {
    var groups = groupsFor(meta, snap);
    var gs = groups.map(function (g) {
      var trips = snap.trips.filter(function (t) { return (t.group_id || '미지정') === g.group_id; });
      var checked = trips.reduce(function (s, t) { return s + (t.assignment_checked === true ? t.people : 0); }, 0);
      return { group: g, trips: trips, checked: snap.reconciled ? checked : null, unconfirmed: snap.reconciled ? g.people - checked : null };
    });
    return {
      status: snap.status, status_ko: STATUS_KO[snap.status], reason: snap.reason,
      final_unload_s: snap.final_unload_s, people_total: snap.people_total, groups_total: snap.groups_total,
      checked: snap.people_with_checked_transport, unconfirmed: snap.people_total - snap.people_with_checked_transport,
      trips: snap.trips, missing: snap.missing_information, assumptions: snap.assumptions, groups: gs, reconciled: snap.reconciled
    };
  }

  function itemKey(x) { return x.code || x.text; }

  function diff(prev, cur, meta) {
    var ch = [];
    if (prev.status !== cur.status) ch.push({ k: 'status', text: '플래너 판정: ' + STATUS_KO[prev.status] + ' → ' + STATUS_KO[cur.status] });
    if (prev.people_total !== cur.people_total) ch.push({ k: 'people_total', text: '전체 인원 ' + prev.people_total + '명 → ' + cur.people_total + '명' });
    if (prev.checked !== cur.checked) ch.push({ k: 'checked', text: '이송 배정 확인 ' + prev.checked + '명 → ' + cur.checked + '명' });
    if (prev.unconfirmed !== cur.unconfirmed) ch.push({ k: 'unconfirmed', text: '이송 수단 미확정 ' + prev.unconfirmed + '명 → ' + cur.unconfirmed + '명' });
    if (prev.final_unload_s !== cur.final_unload_s) ch.push({ k: 'final_unload', text: '전원 하차 예상 ' + fmtT(meta, prev.final_unload_s) + ' → ' + fmtT(meta, cur.final_unload_s) + (cur.final_unload_s === null ? ' (이전 시각은 더 이상 유효하지 않음)' : '') });
    var pm = {}; prev.trips.forEach(function (t) { pm[t.trip_id] = t; });
    var cm = {}; cur.trips.forEach(function (t) { cm[t.trip_id] = t; });
    cur.trips.forEach(function (t) {
      var p = pm[t.trip_id], v = vShort(meta, t.vehicle_id);
      if (!p) { ch.push({ k: 'trip_new', kinds: ['trip_new'], text: v + ' 운행 추가 (' + t.people + '명, ' + fmtT(meta, t.depart_s) + ' 출발)', trip: t.trip_id }); return; }
      var parts = [], kinds = [];
      function part(k, txt) { kinds.push(k); parts.push(txt); }
      if (p.vehicle_id !== t.vehicle_id) part('trip_vehicle', '차량 ' + vShort(meta, p.vehicle_id) + '→' + v);
      if (p.vehicle_status !== t.vehicle_status) part('trip_vstatus', VEHICLE_KO[p.vehicle_status] + '→' + VEHICLE_KO[t.vehicle_status]);
      if (p.assignment_checked !== t.assignment_checked) part('trip_checked', '배정 ' + (t.assignment_checked ? '확인됨' : '해제') + '(' + t.people + '명)');
      if (p.people !== t.people) part('trip_people', '인원 ' + p.people + '→' + t.people + '명');
      if (p.depart_s !== t.depart_s) part('trip_depart', '출발 ' + fmtT(meta, p.depart_s) + '→' + fmtT(meta, t.depart_s));
      if (p.unload_s !== t.unload_s) part('trip_unload', '하차 ' + fmtT(meta, p.unload_s) + '→' + fmtT(meta, t.unload_s));
      if (p.destination_id !== t.destination_id) part('trip_dest', '목적지 ' + dLabel(meta, p.destination_id) + '→' + dLabel(meta, t.destination_id));
      if (p.destination_status !== t.destination_status) part('trip_dstatus', DEST_KO[p.destination_status] + '→' + DEST_KO[t.destination_status]);
      if (parts.length) ch.push({ k: 'trip', kinds: kinds, text: v + ': ' + parts.join(', '), trip: t.trip_id });
    });
    prev.trips.forEach(function (t) { if (!cm[t.trip_id]) ch.push({ k: 'trip_removed', text: vShort(meta, t.vehicle_id) + ' 운행 빠짐 (' + t.people + '명)', trip: t.trip_id }); });
    var pmi = {}; prev.missing.forEach(function (x) { pmi[itemKey(x)] = 1; });
    var cmi = {}; cur.missing.forEach(function (x) { cmi[itemKey(x)] = 1; });
    cur.missing.forEach(function (x) { if (!pmi[itemKey(x)]) ch.push({ k: 'missing_new', text: '새 미확인: ' + x.text }); });
    prev.missing.forEach(function (x) { if (!cmi[itemKey(x)]) ch.push({ k: 'missing_resolved', text: '해소: ' + x.text }); });
    var pa = {}; prev.assumptions.forEach(function (x) { pa[itemKey(x)] = 1; });
    var ca = {}; cur.assumptions.forEach(function (x) { ca[itemKey(x)] = 1; });
    cur.assumptions.forEach(function (x) { if (!pa[itemKey(x)]) ch.push({ k: 'assume_new', text: '새 가정: ' + x.text }); });
    prev.assumptions.forEach(function (x) { if (!ca[itemKey(x)]) ch.push({ k: 'assume_removed', text: '가정 제외: ' + x.text }); });
    return ch;
  }

  function buildModel(v, files) {
    files = files || {};
    var meta = v.meta, B = v.baseline, R = v.revised;
    var cur = summarize(R || B, meta);
    var prev = R ? summarize(B, meta) : null;
    var curAt = R ? (meta.updates.revised || {}).at_s : (meta.updates.baseline || {}).at_s;
    var prevAt = R ? (meta.updates.baseline || {}).at_s : null;
    if (curAt === undefined) curAt = null;

    var requests = [];
    cur.groups.forEach(function (gs) {
      if (gs.unconfirmed > 0) requests.push({
        text: gs.group.request || (gs.group.label + ' 이송 차량'), people: gs.unconfirmed,
        need: gs.group.need, who: role(meta, gs.group.request_role), group: gs.group.label, spoken: gs.group.spoken
      });
    });
    if (!cur.reconciled && cur.unconfirmed > 0) requests.push({ text: '이송 수단 미확정 인원 (그룹별 대조 불가)', people: cur.unconfirmed, need: '미제공', who: role(meta, 'county'), group: '전체', spoken: '미확정 인원' });
    meta.assistance_requests.forEach(function (a) { requests.push({ text: a.text, people: a.people == null ? null : a.people, need: a.need || '', who: role(meta, a.who_role || 'county'), group: a.group || '', spoken: a.spoken || a.text, extra: true }); });

    var conf = [];
    cur.trips.forEach(function (t) {
      var v1 = vShort(meta, t.vehicle_id);
      var named = cur.missing.some(function (x) { return x.text.indexOf(v1) >= 0; });
      if ((t.vehicle_status === 'DELAYED' || t.vehicle_status === 'UNKNOWN') && !named)
        conf.push({ text: v1 + ' ' + (t.vehicle_status === 'DELAYED' ? '지연 — 출발 가능 시각' : '상태') + ' 확인', who: role(meta, (meta.vehicles[t.vehicle_id] || {}).owner_role || 'facility'), k: 'vehicle' });
      if (t.destination_status !== 'CONFIRMED' && t.people > 0 && t.group_id != null) {
        var dl = dLabel(meta, t.destination_id);
        var prior = conf.filter(function (c) { return c.k === 'destination' && c.dest === dl; })[0];
        if (prior) { prior.people += t.people; prior.text = dl + ' 수용 확인 (' + prior.people + '명)'; }
        else conf.push({ text: dl + ' 수용 확인 (' + t.people + '명)', who: role(meta, 'destination') + ' → ' + role(meta, 'county'), k: 'destination', dest: dl, people: t.people });
      }
    });
    cur.missing.forEach(function (x) { conf.push({ text: x.text, who: role(meta, x.who || 'county'), k: 'missing' }); });
    meta.road_status.forEach(function (r) { if (r.status === 'UNKNOWN') conf.push({ text: r.segment + ' 통제 여부', who: role(meta, r.who_role || 'police'), k: 'road' }); });
    conf.push({ text: '배정 확인 ' + cur.checked + '명의 실제 탑승·하차 인원 (계산상 배정 ≠ 탑승·도착)', who: role(meta, 'facility'), k: 'boarding' });

    var sources = {
      model_fire: cur.assumptions.filter(function (a) { return a.kind === 'MODEL_FIRE_RESTRICTION'; }),
      field: meta.field_reports.slice().sort(function (a, b) { return a.at_s - b.at_s; }),
      road: meta.road_status.slice(),
      road_missing: cur.missing.filter(function (x) { return x.kind === 'ROAD_STATUS'; })
    };
    var boarding = cur.assumptions.filter(function (a) { return a.kind !== 'MODEL_FIRE_RESTRICTION'; });

    var model = {
      core_version: CORE_VERSION, meta: meta, single: !R, cur: cur, prev: prev, curAt: curAt, prevAt: prevAt,
      changes: R ? diff(prev, cur, meta) : [], requests: requests, confirmations: conf, sources: sources,
      boarding_assumptions: boarding, warnings: v.warnings.slice(),
      provenance: {
        baseline: { file: files.baseline_name || '(이름 없음)', sha256: files.baseline_text ? sha256(files.baseline_text) : null, schema: B.schema_version, status: B.status, at_s: prevAt === null && !R ? curAt : prevAt, source_label: (meta.updates.baseline || {}).source_label || '' },
        revised: R ? { file: files.revised_name || '(이름 없음)', sha256: files.revised_text ? sha256(files.revised_text) : null, schema: R.schema_version, status: R.status, at_s: curAt, source_label: (meta.updates.revised || {}).source_label || '' } : null,
        meta: { file: files.meta_name || (meta._default ? '(미제공 — 기본값)' : '(이름 없음)'), sha256: files.meta_text ? sha256(files.meta_text) : null }
      }
    };
    model.handoff = buildHandoff(model);
    return model;
  }

  // ---------- 30-second spoken handoff ----------
  function speechUnits(s) {
    var h = (s.match(/[가-힣]/g) || []).length;
    var d = (s.match(/[0-9]/g) || []).length;
    return h + Math.ceil(d * 1.5);
  }
  var HANDOFF_BUDGET = 165; // ≈ 30 s at ~5.5 syllables/s, measured as Hangul syllables + 1.5×digits

  // Korean particle choice by final sound (batchim). Latin/digit endings use their Korean reading.
  function josa(word, withB, without) {
    var w = String(word).replace(/[\s)\]]+$/, '');
    var ch = w.charAt(w.length - 1), code = ch.charCodeAt(0), rieul = false, b;
    if (code >= 0xac00 && code <= 0xd7a3) { var jong = (code - 0xac00) % 28; b = jong !== 0; rieul = jong === 8; }
    else if (/[0-9]/.test(ch)) { b = '013678'.indexOf(ch) >= 0; rieul = '178'.indexOf(ch) >= 0; }
    else if (/[a-z]/i.test(ch)) { b = 'LMNRlmnr'.indexOf(ch) >= 0; rieul = 'LRlr'.indexOf(ch) >= 0; }
    else b = false;
    if (withB === '으로' && rieul) return w + without;
    return w + (b ? withB : without);
  }

  function buildHandoff(m) {
    var meta = m.meta, cur = m.cur, S = [];
    function add(p, t) { if (t) S.push({ p: p, t: t }); }
    add(0, '훈련 상황입니다.');
    add(0, meta.facility.short + ' ' + role(meta, 'facility') + '입니다.');
    var when = spokenT(meta, m.curAt);
    add(0, (when ? when + ' 기준, ' : '') + (m.single ? '현재 상황 보고합니다.' : '변경 사항 보고합니다.'));
    var lost = [];
    if (!m.single) {
      cur.trips.forEach(function (t) {
        var p = m.prev.trips.filter(function (x) { return x.trip_id === t.trip_id; })[0];
        var v = vShort(meta, t.vehicle_id);
        if (t.vehicle_status === 'DELAYED' && (!p || p.vehicle_status !== 'DELAYED'))
          add(1, josa(v, '이', '가') + ' 지연돼 ' + (t.depart_s == null ? '출발 시각을 모릅니다.' : spokenT(meta, t.depart_s) + ' 출발로 늦어졌습니다.'));
        else if (p && typeof p.depart_s === 'number' && typeof t.depart_s === 'number' && t.depart_s > p.depart_s && t.vehicle_status !== 'DELAYED' && t.kind !== 'empty_return')
          add(1, v + ' 출발이 ' + spokenT(meta, p.depart_s) + '에서 ' + spokenT(meta, t.depart_s) + '으로 늦어졌습니다.');
        else if (p && p.depart_s != null && t.depart_s == null && t.vehicle_status !== 'DELAYED' && lost.indexOf(v) < 0) lost.push(v);
        else if (p && p.destination_id !== t.destination_id)
          add(1, (t.group_id ? groupSpoken(meta, cur, t.group_id) + ' ' : '') + t.people + '명 목적지를 ' + josa(dLabel(meta, t.destination_id), '으로', '로') + ' 바꿨습니다.');
      });
    }
    if (lost.length) add(2, lost.join(', ') + ' 출발 시각을 지금 모릅니다.');
    if (cur.status === 'MISSING_INPUT') add(1, '화재 입력 자료가 비어 경로 판정을 못 했습니다. 안전하다는 뜻은 아닙니다.');
    if (cur.status === 'MODEL_SCOPED_NO_ROUTE') add(1, '모델 범위 안에서는 경로가 안 나왔습니다. 실제 도로 상황은 따로 봐야 합니다.');
    if (cur.unconfirmed > 0) {
      var open = cur.reconciled ? cur.groups.filter(function (g) { return g.unconfirmed > 0; }) : [];
      if (open.length === 1) add(1, '전체 ' + cur.people_total + '명 중 ' + open[0].group.spoken + ' ' + open[0].unconfirmed + '명이 아직 이송 수단 확정이 안 됐습니다.');
      else {
        add(1, cur.unconfirmed === cur.people_total ? '전체 ' + cur.people_total + '명 모두 아직 이송 수단 확정이 안 됐습니다.' : '전체 ' + cur.people_total + '명 중 ' + cur.unconfirmed + '명이 아직 이송 수단 확정이 안 됐습니다.');
        if (open.length) add(1, open.map(function (g) { return g.group.spoken + ' ' + g.unconfirmed + '명'; }).join(', ') + '입니다.');
      }
    } else add(1, '전체 ' + cur.people_total + '명 모두 배정은 계산상 확인됐습니다.');
    var byWho = {}, whoOrder = [];
    m.requests.filter(function (r) { return !r.extra; }).forEach(function (r) {
      if (!byWho[r.who]) { byWho[r.who] = []; whoOrder.push(r.who); }
      if (byWho[r.who].indexOf(r.text) < 0) byWho[r.who].push(r.text);
    });
    whoOrder.forEach(function (w) { add(1, byWho[w].join(', ') + ' 요청합니다. ' + w + '에서 확인 부탁드립니다.'); });
    var awaiting = cur.trips.filter(function (t) { return t.destination_status !== 'CONFIRMED' && t.people > 0; });
    var dests = {}; awaiting.forEach(function (t) { dests[dLabel(meta, t.destination_id)] = 1; });
    Object.keys(dests).forEach(function (d) { add(1, d + ' 수용 여부는 아직 확인 전입니다.'); });
    if (cur.final_unload_s == null) add(1, '전원 하차 예상 시각은 지금 모릅니다.');
    else add(2, '전원 하차는 계산상 ' + spokenT(meta, cur.final_unload_s) + (awaiting.length ? '인데, 수용 확인 전 값입니다.' : '입니다.'));
    if (cur.checked > 0) add(2, '배정된 ' + cur.checked + '명도 실제 탑승은 현장에서 따로 확인하겠습니다.');
    m.sources.road.filter(function (r) { return r.status === 'UNKNOWN'; }).slice(0, 1).forEach(function (r) { add(3, r.segment + ' 통제 여부는 아직 모릅니다.'); });
    add(0, '이상입니다.');
    // Drop lowest priority sentences until within budget.
    var keep = S.slice();
    for (var p = 3; p >= 2; p--) {
      while (speechUnits(keep.map(function (x) { return x.t; }).join(' ')) > HANDOFF_BUDGET) {
        var idx = -1;
        for (var i = keep.length - 1; i >= 0; i--) if (keep[i].p === p) { idx = i; break; }
        if (idx < 0) break;
        keep.splice(idx, 1);
      }
    }
    var text = keep.map(function (x) { return x.t; }).join(' ');
    return { text: text, units: speechUnits(text), budget: HANDOFF_BUDGET, over_budget: speechUnits(text) > HANDOFF_BUDGET, est_seconds: Math.round(speechUnits(text) / 5.5) };
  }
  function groupSpoken(meta, cur, gid) {
    var g = cur.groups.filter(function (x) { return x.group.group_id === gid; })[0];
    return g ? g.group.spoken : gid;
  }

  // ---------- HTML rendering ----------
  function kv(k, text, cls) { return '<span data-k="' + esc(k) + '"' + (cls ? ' class="' + cls + '"' : '') + '>' + esc(text) + '</span>'; }
  function tcls(s) { return s == null ? 'unknown' : ''; }

  function header(m, viewTitle, viewId) {
    var meta = m.meta;
    var at = m.curAt;
    var h = '<div class="band">' + esc(meta.exercise_label) + '</div>';
    h += '<header class="hd"><div class="hd-l"><div class="view-name">' + esc(viewTitle) + '</div>';
    h += '<h1>' + esc(meta.facility.label) + '</h1>';
    h += '<div class="sub">사례 ' + kv('case_id', meta.case_id) + ' · ' + esc(meta.time_origin.label || 'T0 미정의') + (meta.time_origin.clock ? ' · T0 = ' + esc(meta.time_origin.clock) + ' (가상 시각)' : '') + '</div></div>';
    h += '<div class="hd-r"><div class="asof-l">' + (m.single ? '보고 시각' : '이번 갱신') + '</div><div class="asof">' + kv('as_of', fmtT(meta, at), tcls(at)) + '</div>';
    if (!m.single) h += '<div class="asof-prev">이전 보고 ' + kv('prev_as_of', fmtT(meta, m.prevAt), tcls(m.prevAt)) + '</div>';
    h += '</div></header>';
    return h;
  }

  function tiles(m) {
    var c = m.cur, meta = m.meta, h = '<section class="tiles">';
    h += '<div class="tile ' + (c.unconfirmed > 0 ? 'alert' : 'ok') + '"><div class="tl">이송 수단 미확정</div><div class="tv">' + kv('unconfirmed', c.unconfirmed) + '<small>명</small></div><div class="tn">전체 ' + kv('people_total', c.people_total) + '명 · ' + kv('groups_total', c.groups_total) + '개 그룹</div>';
    if (m.prev && m.prev.unconfirmed !== c.unconfirmed) h += '<div class="was">이전 ' + kv('prev:unconfirmed', m.prev.unconfirmed + '명') + '</div>';
    h += '</div>';
    h += '<div class="tile"><div class="tl">이송 배정 확인 (계산상)</div><div class="tv">' + kv('checked', c.checked) + '<small>명</small></div><div class="tn">탑승·도착 확인 아님</div>';
    if (m.prev && m.prev.checked !== c.checked) h += '<div class="was">이전 ' + kv('prev:checked', m.prev.checked + '명') + '</div>';
    h += '</div>';
    h += '<div class="tile ' + (c.final_unload_s == null ? 'alert' : '') + '"><div class="tl">전원 하차 예상</div><div class="tv tv-time">' + kv('final_unload', fmtT(meta, c.final_unload_s), tcls(c.final_unload_s)) + '</div><div class="tn">' + esc(c.status_ko) + '</div>';
    if (m.prev && m.prev.final_unload_s !== c.final_unload_s) h += '<div class="was">이전 ' + kv('prev:final_unload', fmtT(meta, m.prev.final_unload_s)) + (c.final_unload_s == null ? ' — 무효' : '') + '</div>';
    h += '</div></section>';
    return h;
  }

  function changesBlock(m, title) {
    var h = '<section class="blk changes"><h2>' + esc(title) + '</h2>';
    if (m.single) h += '<p class="muted">최초 보고 — 비교 대상 없음.</p>';
    else if (!m.changes.length) h += '<p>바뀐 내용 없음.</p>';
    else h += '<ul>' + m.changes.map(function (c) { return '<li data-change="' + esc(c.k) + '">' + esc(c.text) + '</li>'; }).join('') + '</ul>';
    if (m.cur.reason) h += '<p class="reason">플래너 사유(원문): ' + esc(m.cur.reason) + '</p>';
    return h + '</section>';
  }

  function sourcesBlock(m) {
    var meta = m.meta, s = m.sources;
    var h = '<section class="blk sources"><h2>정보 출처 — 섞지 말 것</h2><div class="cols3">';
    h += '<div class="src src-model"><h3>모델 산출 화재 제한<br><small>계산 가정 · 관측 통제 아님</small></h3>';
    h += s.model_fire.length ? '<ul>' + s.model_fire.map(function (a) { return '<li>' + esc(a.text) + '</li>'; }).join('') + '</ul>' : '<p class="muted">해당 가정 없음</p>';
    h += '</div><div class="src src-field"><h3>가상 현장 보고<br><small>훈련용 각본 · 실제 보고 아님</small></h3>';
    h += s.field.length ? '<ul>' + s.field.map(function (f) { return '<li><b>' + esc(fmtT(meta, f.at_s)) + '</b> ' + esc(f.text) + (f.source_role ? ' <i>(' + esc(role(meta, f.source_role)) + ')</i>' : '') + '</li>'; }).join('') + '</ul>' : '<p class="muted">현장 보고 없음</p>';
    h += '</div><div class="src src-road"><h3>도로 상태<br><small>확인 안 된 것은 모름</small></h3>';
    var items = s.road.map(function (r) { return '<li class="' + (r.status === 'UNKNOWN' ? 'unknown' : '') + '">' + esc(r.segment) + ': ' + esc(ROAD_KO[r.status]) + (r.note ? ' — ' + esc(r.note) : '') + '</li>'; })
      .concat(s.road_missing.map(function (x) { return '<li class="unknown">' + esc(x.text) + '</li>'; }));
    h += items.length ? '<ul>' + items.join('') + '</ul>' : '<p class="muted">도로 정보 미제공 — 모름으로 취급</p>';
    return h + '</div></div></section>';
  }

  function tripRows(m, compact) {
    var meta = m.meta;
    return m.cur.trips.map(function (t) {
      var g = t.kind === 'empty_return' ? '빈 차 복귀' : groupSpoken(meta, m.cur, t.group_id);
      var r = '<tr class="' + (t.assignment_checked ? '' : 'row-open') + '"><td><b>' + esc(vLabel(meta, t.vehicle_id)) + '</b></td>';
      r += '<td class="st st-' + t.vehicle_status + '">' + kv('trip:' + t.trip_id + ':vstatus', VEHICLE_KO[t.vehicle_status]) + '</td>';
      r += '<td>' + esc(g) + ' ' + kv('trip:' + t.trip_id + ':people', t.people + '명') + '</td>';
      r += '<td>' + kv('trip:' + t.trip_id + ':checked', t.assignment_checked === true ? '확인' : t.assignment_checked === false ? '미확정' : '모름', t.assignment_checked === true ? '' : 'unknown') + '</td>';
      if (!compact) r += '<td>' + esc(fmtDur(t.boarding_s)) + '</td>';
      r += '<td>' + kv('trip:' + t.trip_id + ':depart', fmtT(meta, t.depart_s), tcls(t.depart_s)) + '</td>';
      r += '<td>' + kv('trip:' + t.trip_id + ':unload', fmtT(meta, t.unload_s), tcls(t.unload_s)) + '</td>';
      r += '<td>' + esc(dLabel(meta, t.destination_id)) + ' <span class="ds ds-' + t.destination_status + '">' + kv('trip:' + t.trip_id + ':dstatus', DEST_KO[t.destination_status]) + '</span></td></tr>';
      return r;
    }).join('');
  }

  // Printed footer: one line per distinct notice; per-trip alias notes collapsed (full list stays in reports).
  function compactWarnings(ws) {
    var out = [], aliases = {}, seen = {};
    ws.forEach(function (w) {
      var m = /필드 별칭 (\S+ → \S+)/.exec(w);
      if (m) { aliases[m[1]] = (aliases[m[1]] || 0) + 1; return; }
      var k = w.replace(/^(기준\(baseline\)|변경\(revised\)): /, '');
      if (seen[k]) return; seen[k] = 1; out.push(k);
    });
    var al = Object.keys(aliases);
    if (al.length) out.push('필드 별칭으로 읽음: ' + al.join(', '));
    return out;
  }

  function provFooter(m) {
    var p = m.provenance, meta = m.meta;
    function one(lbl, x) {
      if (!x) return '';
      return '<div>' + esc(lbl) + ': ' + esc(x.source_label || '') + ' · 보고 ' + esc(fmtT(meta, x.at_s)) + ' · <code>' + esc(x.file) + '</code> · sha256 ' + esc(x.sha256 ? x.sha256.slice(0, 12) : '계산 안 함') + ' · ' + esc(x.schema) + ' · ' + esc(x.status) + '</div>';
    }
    var h = '<footer class="prov"><div class="prov-h">출처 (Provenance)</div>';
    h += one(m.single ? '보고' : '기준(이전)', p.baseline) + one('변경(현재)', p.revised);
    h += '<div>메타: <code>' + esc(p.meta.file) + '</code>' + (p.meta.sha256 ? ' · sha256 ' + esc(p.meta.sha256.slice(0, 12)) : '') + ' · ' + esc(CORE_VERSION) + ' · 시각은 분 단위 올림</div>';
    var cw = compactWarnings(m.warnings);
    if (cw.length) h += '<div class="warn">주의: ' + cw.map(esc).join(' / ') + '</div>';
    h += '<div class="disc">연구용 훈련 시안 · 기관 승인·검증 없음 · 실명·연락처·진료기록 입력 금지 · ' + esc(meta.exercise_label) + '</div>';
    return h + '</footer>';
  }

  // Deterministic print density: more rows → slightly smaller print type so the A4 sheet stays one page.
  function density(m) {
    var src = Math.max(m.sources.model_fire.length, m.sources.field.length, m.sources.road.length + m.sources.road_missing.length, 1);
    var asChars = m.boarding_assumptions.reduce(function (n, x) { return n + x.text.length; }, 0);
    var score = asChars / 110 + m.changes.length + m.confirmations.length + m.cur.trips.length * 1.6 + m.requests.length + src * 1.5 + compactWarnings(m.warnings).join(' / ').length / 90;
    return score > 27 ? 'density-2' : score > 18 ? 'density-1' : 'density-0';
  }

  function renderCounty(m) {
    var meta = m.meta, c = m.cur;
    var h = '<article class="sheet view-county ' + density(m) + '" data-view="county">' + header(m, '시군 재난안전 담당자용 · 시설 이송 상황 인계', 'county');
    h += changesBlock(m, m.single ? '1. 현재 상황' : '1. 무엇이 바뀌었나');
    h += tiles(m);
    h += '<section class="blk"><h2>2. 지원 요청 · 확인할 사람</h2>';
    if (m.requests.length) {
      h += '<table class="t"><thead><tr><th>요청</th><th>인원</th><th>필요 조건</th><th>확인 주체</th></tr></thead><tbody>';
      h += m.requests.map(function (r, i) { return '<tr><td><b>' + esc(r.text) + '</b></td><td>' + kv('req:' + i + ':people', r.people == null ? '모름' : r.people + '명') + '</td><td>' + esc(r.need) + '</td><td>' + esc(r.who) + '</td></tr>'; }).join('');
      h += '</tbody></table>';
    } else h += '<p>추가 지원 요청 없음 (현재 계산 기준).</p>';
    h += '</section>';
    h += '<section class="blk"><h2>3. 아직 확인 안 된 것</h2><table class="t conf"><thead><tr><th></th><th>확인할 내용</th><th>누가</th></tr></thead><tbody>';
    h += m.confirmations.map(function (x) { return '<tr><td class="box">□</td><td>' + esc(x.text) + '</td><td>' + esc(x.who) + '</td></tr>'; }).join('');
    h += '</tbody></table></section>';
    h += sourcesBlock(m);
    h += '<section class="blk"><h2>4. 차량별 (현재 기준)</h2><table class="t trips"><thead><tr><th>차량</th><th>상태</th><th>대상</th><th>배정</th><th>출발</th><th>하차</th><th>목적지</th></tr></thead><tbody>' + tripRows(m, true) + '</tbody></table></section>';
    h += '<section class="blk handoff"><h2>30초 구두 인계 (시설 → 시군)</h2><p data-k="handoff">' + esc(m.handoff.text) + '</p><div class="muted small">약 ' + m.handoff.est_seconds + '초 분량 (음절 기준 추정)</div></section>';
    h += provFooter(m);
    return h + '</article>';
  }

  function renderFacility(m) {
    var meta = m.meta, c = m.cur;
    var h = '<article class="sheet view-facility ' + density(m) + '" data-view="facility">' + header(m, '시설 담당자용 · 이송 준비 현황', 'facility');
    h += tiles(m);
    h += '<section class="blk"><h2>1. 그룹별 인원 · 이송 필요</h2><table class="t"><thead><tr><th>그룹</th><th>인원</th><th>이동·이송 필요</th><th>배정 확인</th><th>미확정</th><th>차량</th></tr></thead><tbody>';
    h += c.groups.map(function (gs) {
      var g = gs.group;
      var veh = gs.trips.map(function (t) { return vShort(meta, t.vehicle_id) + '(' + VEHICLE_KO[t.vehicle_status] + ')'; }).join(', ') || '없음';
      return '<tr class="' + (gs.unconfirmed ? 'row-open' : '') + '"><td><b>' + esc(g.label) + '</b></td><td>' + kv('group:' + g.group_id + ':people', g.people + '명') + '</td><td>' + esc(g.need) + '</td><td>' + kv('group:' + g.group_id + ':checked', gs.checked == null ? '대조 불가' : gs.checked + '명') + '</td><td>' + kv('group:' + g.group_id + ':unconfirmed', gs.unconfirmed == null ? '대조 불가' : gs.unconfirmed + '명', gs.unconfirmed ? 'hot' : '') + '</td><td>' + esc(veh) + '</td></tr>';
    }).join('');
    h += '</tbody></table></section>';
    h += '<section class="blk"><h2>2. 차량 · 출발 · 하차</h2><table class="t trips"><thead><tr><th>차량</th><th>상태</th><th>대상</th><th>배정</th><th>탑승 가정</th><th>출발</th><th>하차</th><th>목적지</th></tr></thead><tbody>' + tripRows(m, false) + '</tbody></table></section>';
    h += '<section class="blk two"><div><h2>3. 탑승·운행 전제 (계산 가정)</h2>';
    h += m.boarding_assumptions.length ? '<ul>' + m.boarding_assumptions.map(function (a) { return '<li>' + esc(a.text) + '</li>'; }).join('') + '</ul>' : '<p class="muted">전제 미제공</p>';
    h += '</div><div><h2>4. 지금 확인할 것</h2><ul class="chk">' + m.confirmations.map(function (x) { return '<li>□ ' + esc(x.text) + ' <i>— ' + esc(x.who) + '</i></li>'; }).join('') + '</ul></div></section>';
    h += changesBlock(m, m.single ? '5. 현재 상황' : '5. 이전 보고 대비 바뀐 것');
    h += sourcesBlock(m);
    h += provFooter(m);
    return h + '</article>';
  }

  function renderError(errors, warnings) {
    var h = '<article class="sheet view-error" data-view="error"><div class="band">표시 중단 — 입력 오류</div><h1>브리핑을 만들 수 없습니다</h1><p>이전에 표시하던 내용은 지웠습니다. 아래 오류를 고친 뒤 다시 불러오세요.</p><ul class="errs">';
    h += errors.map(function (e) { return '<li>' + esc(e) + '</li>'; }).join('') + '</ul>';
    if (warnings && warnings.length) h += '<h2>주의</h2><ul>' + warnings.map(function (e) { return '<li>' + esc(e) + '</li>'; }).join('') + '</ul>';
    return h + '</article>';
  }

  // convenience: everything in one call
  function brief(inputs) {
    var p = function (t) { return t == null ? null : JSON.parse(t); };
    var b, r, mt;
    try { b = p(inputs.baseline_text); r = p(inputs.revised_text); mt = p(inputs.meta_text); }
    catch (e) { return { ok: false, errors: ['JSON 구문 오류: ' + e.message], warnings: [] }; }
    if (b == null) return { ok: false, errors: ['기준(baseline) 파일 없음'], warnings: [] };
    var v = validateBrief(b, r, mt);
    if (!v.ok) return v;
    var m = buildModel(v, inputs);
    return { ok: true, model: m, warnings: v.warnings, county: renderCounty(m), facility: renderFacility(m), handoff: m.handoff };
  }

  return {
    CORE_VERSION: CORE_VERSION, PLANNER_STATUSES: PLANNER_STATUSES, REQUIRED: REQUIRED,
    normalizePlanner: normalizePlanner, normalizeMeta: normalizeMeta, validateBrief: validateBrief,
    buildModel: buildModel, renderCounty: renderCounty, renderFacility: renderFacility, renderError: renderError,
    brief: brief, sha256: sha256, fmtT: fmtT, speechUnits: speechUnits, esc: esc
  };
});
