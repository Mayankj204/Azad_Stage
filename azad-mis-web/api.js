/**
 * Azad Foundation MIS - API Client
 * Provides fetch-based methods to communicate with the FastAPI backend.
 */

// Auto-detect API base: use relative path when served from backend, absolute for file://
var API_BASE = (window.location.protocol === 'file:')
  ? 'http://localhost:8000/api'
  : (window.location.origin + '/api');

// Store JWT token
var authToken = localStorage.getItem('azadToken') || null;

/**
 * Generic API request handler
 */
function apiRequest(method, path, body) {
  var headers = { 'Content-Type': 'application/json' };
  if (authToken) {
    headers['Authorization'] = 'Bearer ' + authToken;
  }
  var opts = { method: method, headers: headers };
  if (body && method !== 'GET') {
    opts.body = JSON.stringify(body);
  }
  return fetch(API_BASE + path, opts)
    .then(function(resp) {
      if (!resp.ok) {
        return resp.text().then(function(text) {
          try {
            var err = JSON.parse(text);
            throw new Error(_formatApiDetail(err.detail, resp.status));
          } catch(e) {
            if (e.message && !e.message.startsWith('Unexpected')) throw e;
            throw new Error('Server Error (' + resp.status + '): ' + text.substring(0, 200));
          }
        });
      }
      return resp.json();
    });
}

/**
 * Convert FastAPI's `detail` field into a human-readable string.
 *
 * FastAPI returns three shapes for `detail`:
 *  - a string (HTTPException raised by route code) — already readable
 *  - an array of {loc, msg, type} objects (Pydantic 422 validation errors)
 *  - any other shape (defensive fallback)
 *
 * Before this helper, `new Error(err.detail)` on an array stringified to
 * `"[object Object]"`, which is what the user saw on a draft save with an
 * empty DOB. Now we surface every offending field + reason.
 */
function _formatApiDetail(detail, status) {
  if (detail == null) return 'API Error ' + status;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    var parts = detail.map(function(d) {
      if (!d || typeof d !== 'object') return String(d);
      // `loc` is typically ['body', 'field_name']; we want the last segment
      var loc = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : d.loc;
      var msg = d.msg || d.message || 'Invalid value';
      return loc ? (loc + ': ' + msg) : msg;
    });
    return parts.join('\n');
  }
  // Object detail — best-effort stringify
  try { return JSON.stringify(detail); } catch (e) { return 'API Error ' + status; }
}

function apiGet(path) { return apiRequest('GET', path); }
function apiPost(path, data) { return apiRequest('POST', path, data); }
function apiPut(path, data) { return apiRequest('PUT', path, data); }
function apiPatch(path, data) { return apiRequest('PATCH', path, data); }
function apiDelete(path) { return apiRequest('DELETE', path); }

/**
 * File upload helper
 */
function apiUpload(path, formData) {
  var headers = {};
  if (authToken) {
    headers['Authorization'] = 'Bearer ' + authToken;
  }
  return fetch(API_BASE + path, {
    method: 'POST',
    headers: headers,
    body: formData
  }).then(function(resp) {
    if (!resp.ok) {
      return resp.json().then(function(err) {
        throw new Error(err.detail || 'Upload Error');
      });
    }
    return resp.json();
  });
}

// ===== AUTH =====
function apiLogin(email, password) {
  return apiPost('/auth/login', { email: email, password: password })
    .then(function(data) {
      authToken = data.token;
      localStorage.setItem('azadToken', data.token);
      localStorage.setItem('azadUser', JSON.stringify(data.user));
      return data;
    });
}

function apiLogout() {
  authToken = null;
  localStorage.removeItem('azadToken');
  localStorage.removeItem('azadUser');
}

// Forgot Password — fetches a captcha token + question, then submits it
// alongside the user's answer. Server emails a freshly generated password.
function apiGetCaptcha() {
  return fetch(API_BASE + '/auth/captcha', { method: 'GET' })
    .then(function(resp) {
      if (!resp.ok) throw new Error('captcha-failed');
      return resp.json();
    });
}

function apiForgotPassword(email, captchaToken, captchaAnswer) {
  return apiPost('/auth/forgot-password', {
    email: email,
    captcha_token: captchaToken,
    captcha_answer: captchaAnswer
  });
}

// ===== DASHBOARD =====
function _dashFilterQs(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.state) qs.push('state=' + encodeURIComponent(params.state));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.centre) qs.push('centre=' + encodeURIComponent(params.centre));
    if (params.date_from) qs.push('date_from=' + params.date_from);
    if (params.date_to) qs.push('date_to=' + params.date_to);
  }
  return qs.length ? '?' + qs.join('&') : '';
}
function apiDashboardStats(params) { return apiGet('/dashboard/stats' + _dashFilterQs(params)); }
function apiDashboardCharts(params) { return apiGet('/dashboard/charts' + _dashFilterQs(params)); }
function apiDrillDownFlps(chart, value) { return apiGet('/dashboard/drill-down/flps?chart=' + encodeURIComponent(chart) + '&value=' + encodeURIComponent(value)); }

// ===== GEOGRAPHY =====
function apiStates(params) {
  var qs = [];
  if (params) {
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/states' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateState(data) { return apiPost('/states', data); }
function apiDistricts(params) {
  var qs = [];
  if (params) {
    if (params.state_id) qs.push('state_id=' + params.state_id);
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/districts' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateDistrict(data) { return apiPost('/districts', data); }
function apiCities(params) {
  var qs = [];
  if (params) {
    if (params.district_id) qs.push('district_id=' + params.district_id);
    if (params.state_id) qs.push('state_id=' + params.state_id);
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/cities' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateCity(data) { return apiPost('/cities', data); }
function apiUpdateState(id, data) { return apiPut('/states/' + id, data); }
function apiUpdateDistrict(id, data) { return apiPut('/districts/' + id, data); }
function apiUpdateCity(id, data) { return apiPut('/cities/' + id, data); }

// ===== CENTRES & BATCHES =====
function apiCentres(params) {
  var qs = [];
  if (params) {
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/centres' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateCentre(data) { return apiPost('/centres', data); }
function apiBatches(params) {
  var qs = [];
  if (params) {
    if (params.centre_id) qs.push('centre_id=' + params.centre_id);
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/batches' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateBatch(data) { return apiPost('/batches', data); }
function apiUpdateCentre(id, data) { return apiPut('/centres/' + id, data); }
function apiUpdateBatch(id, data) { return apiPut('/batches/' + id, data); }
function apiUnallocatedFlps(batchId) { return apiGet('/batches/' + batchId + '/unallocated-flps'); }
function apiBatchAllocate(batchId, flpIds) { return apiPost('/batches/' + batchId + '/allocate', { flp_ids: flpIds }); }

// ===== NEW GEOGRAPHY (code-based) =====
function apiGeoStates(params) {
  var qs = [];
  if (params) { if (params.page) qs.push('page=' + params.page); if (params.limit) qs.push('limit=' + params.limit); }
  return apiGet('/geo/states' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiGeoCreateState(data) { return apiPost('/geo/states', data); }
function apiGeoUpdateState(code, data) { return apiPut('/geo/states/' + encodeURIComponent(code), data); }

function apiGeoDistricts(params) {
  var qs = [];
  if (params) { if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code)); if (params.page) qs.push('page=' + params.page); if (params.limit) qs.push('limit=' + params.limit); }
  return apiGet('/geo/districts' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiGeoCreateDistrict(data) { return apiPost('/geo/districts', data); }
function apiGeoUpdateDistrict(code, data) { return apiPut('/geo/districts/' + encodeURIComponent(code), data); }

function apiGeoCentres(params) {
  var qs = [];
  if (params) { if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code)); if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code)); if (params.page) qs.push('page=' + params.page); if (params.limit) qs.push('limit=' + params.limit); }
  return apiGet('/geo/centres' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiGeoCreateCentre(data) { return apiPost('/geo/centres', data); }
function apiGeoUpdateCentre(code, data) { return apiPut('/geo/centres/' + encodeURIComponent(code), data); }

function apiGeoAreas(params) {
  var qs = [];
  if (params) { if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code)); if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code)); if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code)); if (params.page) qs.push('page=' + params.page); if (params.limit) qs.push('limit=' + params.limit); }
  return apiGet('/geo/areas' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiGeoCreateArea(data) { return apiPost('/geo/areas', data); }
function apiGeoUpdateArea(code, data) { return apiPut('/geo/areas/' + encodeURIComponent(code), data); }

// Dropdown helpers (compact, no pagination)
function apiGeoDropdownStates() { return apiGet('/geo/dropdown/states'); }
function apiGeoDropdownDistricts(stateCode) { return apiGet('/geo/dropdown/districts?state_code=' + encodeURIComponent(stateCode)); }
function apiGeoDropdownCentres(districtCode) { return apiGet('/geo/dropdown/centres?district_code=' + encodeURIComponent(districtCode)); }
function apiGeoDropdownCentresByState(stateCode) { return apiGet('/geo/dropdown/centres?state_code=' + encodeURIComponent(stateCode)); }
function apiGeoDropdownAreas(centreCode) { return apiGet('/geo/dropdown/areas?centre_code=' + encodeURIComponent(centreCode)); }

// ===== ROLES & USERS =====
function apiRoles(params) {
  var qs = [];
  if (params) {
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/roles' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateRole(data) { return apiPost('/roles', data); }
function apiUsers(params) {
  var qs = [];
  if (params) {
    if (params.role_id) qs.push('role_id=' + params.role_id);
    if (params.status) qs.push('status=' + params.status);
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.geo_scope) qs.push('geo_scope=' + encodeURIComponent(params.geo_scope));
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/users' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateUser(data) { return apiPost('/users', data); }
function apiRoleDetail(id) { return apiGet('/roles/' + id); }
function apiUpdateRole(id, data) { return apiPut('/roles/' + id, data); }
function apiUserDetail(id) { return apiGet('/users/' + id); }
function apiUpdateUser(id, data) { return apiPut('/users/' + id, data); }
function apiDeleteUser(id) { return apiDelete('/users/' + id); }
function apiResetPassword(id) { return apiPost('/users/' + id + '/reset-password', {}); }

// ===== FLPs =====
function apiFlps(params) {
  var qs = [];
  if (params) {
    if (params.centre_id) qs.push('centre_id=' + params.centre_id);
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch_id) qs.push('batch_id=' + params.batch_id);
    if (params.status) qs.push('status=' + params.status);
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.date_from) qs.push('date_from=' + params.date_from);
    if (params.date_to) qs.push('date_to=' + params.date_to);
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/flps' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiFlpDetail(id) { return apiGet('/flps/' + id); }
function apiCreateFlp(data) { return apiPost('/flps', data); }
function apiUpdateFlp(id, data) { return apiPut('/flps/' + id, data); }
function apiUpdateFlpBank(id, data) { return apiPut('/flps/' + id + '/bank', data); }
function apiUpdateFlpEmployment(id, data) { return apiPut('/flps/' + id + '/employment', data); }
function apiFlpFamily(id) { return apiGet('/flps/' + id + '/family'); }
function apiAddFamilyMember(id, data) { return apiPost('/flps/' + id + '/family', data); }
function apiDeleteFamilyMember(flpId, memberId) { return apiDelete('/flps/' + flpId + '/family/' + memberId); }
function apiFlpDocuments(id) { return apiGet('/flps/' + id + '/documents'); }
function apiFlpLog(id) { return apiGet('/flps/' + id + '/log'); }
// Emergency Contacts
function apiFlpEmergencyContacts(id) { return apiGet('/flps/' + id + '/emergency-contacts'); }
function apiAddEmergencyContact(id, data) { return apiPost('/flps/' + id + '/emergency-contacts', data); }
function apiDeleteEmergencyContact(flpId, contactId) { return apiDelete('/flps/' + flpId + '/emergency-contacts/' + contactId); }
// Contribution Payments
function apiFlpContributions(id) { return apiGet('/flps/' + id + '/contributions'); }
function apiAddContribution(id, data) { return apiPost('/flps/' + id + '/contributions', data); }
// Photo upload
function apiUploadFlpPhoto(id, file) {
  var formData = new FormData();
  formData.append('file', file);
  return apiUpload('/flps/' + id + '/photo', formData);
}
// Credential
function apiUpdateFlpCredential(id, data) { return apiPut('/flps/' + id + '/credential', data); }

// ===== TRAINING TOPICS (Master) =====
function apiTrainingTopics(params) {
  var qs = [];
  if (params) {
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/training-topics' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateTopic(data) { return apiPost('/training-topics', data); }
function apiUpdateTopic(id, data) { return apiPut('/training-topics/' + id, data); }
function apiDeleteTopic(id) { return apiDelete('/training-topics/' + id); }

// ===== TRAININGS =====
function apiTrainings(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.batch_id) qs.push('batch_id=' + params.batch_id);
    if (params.centre_id) qs.push('centre_id=' + params.centre_id);
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.phase) qs.push('phase=' + encodeURIComponent(params.phase));
    if (params.date_from) qs.push('date_from=' + params.date_from);
    if (params.date_to) qs.push('date_to=' + params.date_to);
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/trainings' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiTrainingDetail(id) { return apiGet('/trainings/' + id); }
function apiCreateTraining(data) { return apiPost('/trainings', data); }
function apiAssignParticipants(trainingId, flpIds) { return apiPost('/trainings/' + trainingId + '/participants', { flp_ids: flpIds }); }

// ===== SURVEYS =====
function apiSurveys(params) {
  var qs = [];
  if (params) {
    if (params.flp_id) qs.push('flp_id=' + params.flp_id);
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.flp_name) qs.push('flp_name=' + encodeURIComponent(params.flp_name));
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.state) qs.push('state=' + encodeURIComponent(params.state));
    if (params.date_from) qs.push('date_from=' + params.date_from);
    if (params.date_to) qs.push('date_to=' + params.date_to);
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/surveys' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiSurveyDetail(id) { return apiGet('/surveys/' + id); }
function apiUpdateSurveyStatus(id, status) { return apiPut('/surveys/' + id + '/status', { status: status }); }

// ===== WWW PIPELINE =====
function apiWww(params) {
  var qs = [];
  if (params) {
    if (params.stage) qs.push('stage=' + params.stage);
    if (params.training_pref) qs.push('training_pref=' + encodeURIComponent(params.training_pref));
    if (params.state) qs.push('state=' + encodeURIComponent(params.state));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/www' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiUpdateWwwStage(id, stage) { return apiPut('/www/' + id + '/stage', { stage: stage }); }
function apiWwwStats() { return apiGet('/www/stats'); }

// ===== ASSESSMENTS =====
function apiAssessments(params) {
  var qs = [];
  if (params) {
    if (params.flp_id) qs.push('flp_id=' + params.flp_id);
    if (params.type) qs.push('type=' + encodeURIComponent(params.type));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.location) qs.push('location=' + encodeURIComponent(params.location));
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.flp_name) qs.push('flp_name=' + encodeURIComponent(params.flp_name));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/assessments' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAssessmentDetail(id) { return apiGet('/assessments/' + id); }
function apiCreateAssessment(data) { return apiPost('/assessments', data); }
function apiUpdateAssessment(id, data) { return apiPut('/assessments/' + id, data); }
function apiAssessmentCompare(preId) { return apiGet('/assessments/' + preId + '/compare'); }
function apiBaselineReport(params) {
  var qs = [];
  if (params) {
    if (params.state_code)    qs.push('state_code='    + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.centre_code)   qs.push('centre_code='   + encodeURIComponent(params.centre_code));
    if (params.batch_id)      qs.push('batch_id='      + encodeURIComponent(params.batch_id));
  }
  return apiGet('/assessments/reports/baseline' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiEmpanelledFlps(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.location) qs.push('location=' + encodeURIComponent(params.location));
  }
  return apiGet('/assessments/empanelled' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiFlpsWithPre(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.location) qs.push('location=' + encodeURIComponent(params.location));
  }
  return apiGet('/assessments/with-pre' + (qs.length ? '?' + qs.join('&') : ''));
}

// ===== ACTIVITY LOG =====
function apiSystemLog(params) {
  var qs = [];
  if (params) {
    if (params.user_id) qs.push('user_id=' + params.user_id);
    if (params.action) qs.push('action=' + encodeURIComponent(params.action));
    if (params.source) qs.push('source=' + encodeURIComponent(params.source));
    if (params.start_date) qs.push('start_date=' + params.start_date);
    if (params.end_date) qs.push('end_date=' + params.end_date);
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/activity-log' + (qs.length ? '?' + qs.join('&') : ''));
}

// ===== TARGETS =====
function apiTargets(params) {
  var qs = [];
  if (params) {
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.centre_id) qs.push('centre_id=' + params.centre_id);
    if (params.target_month) qs.push('target_month=' + encodeURIComponent(params.target_month));
  }
  return apiGet('/targets' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiSetTargets(data) { return apiPost('/targets', data); }
function apiCopyTargets(data) { return apiPost('/targets/copy', data); }
function apiTargetAchievements(params) {
  var qs = [];
  if (params) {
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.centre_id) qs.push('centre_id=' + params.centre_id);
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.target_month) qs.push('target_month=' + encodeURIComponent(params.target_month));
    // 2026-06-30 — date-range params were being silently dropped by the
    // whitelist; the backend honours them but only sees them if we forward.
    if (params.date_from) qs.push('date_from=' + encodeURIComponent(params.date_from));
    if (params.date_to) qs.push('date_to=' + encodeURIComponent(params.date_to));
  }
  return apiGet('/targets/achievements' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiFlpTargetAllocation(centreCode, targetMonth) {
  return apiGet('/targets/flp-targets?centre_code=' + encodeURIComponent(centreCode) + '&target_month=' + encodeURIComponent(targetMonth));
}
function apiSetFlpTargets(data) { return apiPost('/targets/flp-targets', data); }

function apiFlpPerformance(params) {
  var qs = [];
  if (params) {
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.centre_id) qs.push('centre_id=' + params.centre_id);
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.target_month) qs.push('target_month=' + encodeURIComponent(params.target_month));
    if (params.date_from) qs.push('date_from=' + encodeURIComponent(params.date_from));
    if (params.date_to) qs.push('date_to=' + encodeURIComponent(params.date_to));
  }
  return apiGet('/targets/flp-performance' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiPublishTargets(data) { return apiPost('/targets/publish', data); }
function apiReports(params) {
  var qs = [];
  if (params) {
    if (params.centre_id) qs.push('centre_id=' + params.centre_id);
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.flp_id) qs.push('flp_id=' + params.flp_id);
    if (params.report_month) qs.push('report_month=' + encodeURIComponent(params.report_month));
  }
  return apiGet('/targets/reports' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiSaveReport(data) { return apiPost('/targets/reports', data); }
function apiSubmitReport(data) { return apiPost('/targets/reports/submit', data); }

// ---- Notifications ----
function apiGetNotifications(userId, limit) {
  var qs = 'user_id=' + userId;
  if (limit) qs += '&limit=' + limit;
  return apiGet('/notifications?' + qs);
}
function apiGetUnreadCount(userId) {
  return apiGet('/notifications/unread-count?user_id=' + userId);
}
function apiMarkNotificationRead(notificationId) {
  return apiPost('/notifications/read/' + notificationId);
}
function apiMarkAllNotificationsRead(userId) {
  return apiPost('/notifications/read-all?user_id=' + userId);
}

// ---- MGJ ----
function apiMgjList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    // 2026-06-03: centre_code was silently dropped here for months — picking
    // North Delhi from the Centre filter would still return all Delhi
    // members because the param never reached the API. The backend supports
    // centre_code = exact match (see routes/mgj.py:151-152) and the loader
    // (loadMgjListData) was already populating params.centre_code from the
    // dropdown; only this wrapper was the gap. Same fix for include_dropout
    // which the list page sets to true but was also being dropped, masking
    // dropout members the page is supposed to show.
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.date_from) qs.push('date_from=' + params.date_from);
    if (params.date_to) qs.push('date_to=' + params.date_to);
    if (params.include_dropout) qs.push('include_dropout=' + encodeURIComponent(params.include_dropout));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/mgj' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiMgjDetail(id) { return apiGet('/mgj/' + id); }
function apiCreateMgj(data) { return apiPost('/mgj', data); }
function apiUpdateMgj(id, data) { return apiPut('/mgj/' + id, data); }
// 2026-07-06: Photo upload — previously MISSING entirely (the edit form
// only previewed the picked file locally; nothing was ever sent, so
// mgj_members.photo_url stayed NULL). Mirrors apiUploadFlpPhoto.
function apiMgjUploadPhoto(id, file) {
  var fd = new FormData(); fd.append('file', file);
  return apiUpload('/mgj/' + id + '/photo', fd);
}

// MGJ member per-member education history (added 2026-05-27)
function apiMgjListEducation(memberId)        { return apiGet('/mgj/' + memberId + '/education'); }
function apiMgjAddEducation(memberId, entry)  { return apiPost('/mgj/' + memberId + '/education', entry); }
function apiMgjDeleteEducation(entryId)       { return apiDelete('/mgj/education/' + entryId); }
function apiDeleteMgj(id) { return apiDelete('/mgj/' + id); }

// ---- MGJ Case Studies (2026-05-30) ----
// Single-row table per case study; narrative fields stored as columns;
// attachments as JSONB array. See routes/mgj_case_study.py.
function apiMgjCaseStudyList(params) {
  var qs = [];
  if (params) {
    if (params.state_code)  qs.push('state_code='  + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.category)    qs.push('category='    + encodeURIComponent(params.category));
    if (params.status)      qs.push('status='      + encodeURIComponent(params.status));
    if (params.q)           qs.push('q='           + encodeURIComponent(params.q));
    if (params.page)        qs.push('page='        + params.page);
    if (params.limit)       qs.push('limit='       + params.limit);
  }
  return apiGet('/mgj-case-studies' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiMgjCaseStudyDetail(id)        { return apiGet('/mgj-case-studies/' + id); }
function apiMgjCaseStudyCreate(data)      { return apiPost('/mgj-case-studies', data); }
function apiMgjCaseStudyUpdate(id, data)  { return apiPut('/mgj-case-studies/' + id, data); }
function apiMgjCaseStudyDelete(id)        { return apiDelete('/mgj-case-studies/' + id); }
function apiMgjCaseStudyUploadPhoto(id, file) {
  var fd = new FormData(); fd.append('file', file);
  return apiUpload('/mgj-case-studies/' + id + '/photo', fd);
}
function apiMgjCaseStudyUploadAttachment(id, file) {
  var fd = new FormData(); fd.append('file', file);
  return apiUpload('/mgj-case-studies/' + id + '/attachment', fd);
}

// ---- AK Case Studies (2026-06-05) ----
// Cloned from MGJ above; same shape, different endpoint prefix.
// FK column is `leader_id` (not member_id) because the AK table is
// `ak_leaders`.
function apiAkCaseStudyList(params) {
  var qs = [];
  if (params) {
    if (params.state_code)  qs.push('state_code='  + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch_id)    qs.push('batch_id='    + params.batch_id);
    if (params.category)    qs.push('category='    + encodeURIComponent(params.category));
    if (params.status)      qs.push('status='      + encodeURIComponent(params.status));
    if (params.q)           qs.push('q='           + encodeURIComponent(params.q));
    if (params.page)        qs.push('page='        + params.page);
    if (params.limit)       qs.push('limit='       + params.limit);
  }
  return apiGet('/ak-case-studies' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkCaseStudyDetail(id)        { return apiGet('/ak-case-studies/' + id); }
function apiAkCaseStudyCreate(data)      { return apiPost('/ak-case-studies', data); }
function apiAkCaseStudyUpdate(id, data)  { return apiPut('/ak-case-studies/' + id, data); }
function apiAkCaseStudyDelete(id)        { return apiDelete('/ak-case-studies/' + id); }
function apiAkCaseStudyUploadPhoto(id, file) {
  var fd = new FormData(); fd.append('file', file);
  return apiUpload('/ak-case-studies/' + id + '/photo', fd);
}
function apiAkCaseStudyUploadAttachment(id, file) {
  var fd = new FormData(); fd.append('file', file);
  return apiUpload('/ak-case-studies/' + id + '/attachment', fd);
}

// ---- FLP Case Studies (2026-06-05) ----
// Cloned from MGJ/AK above; same shape, FLP endpoint prefix. FK column
// is `flp_id` because the backing table is `flps`.
function apiFlpCaseStudyList(params) {
  var qs = [];
  if (params) {
    if (params.state_code)  qs.push('state_code='  + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch_id)    qs.push('batch_id='    + params.batch_id);
    if (params.category)    qs.push('category='    + encodeURIComponent(params.category));
    if (params.status)      qs.push('status='      + encodeURIComponent(params.status));
    if (params.q)           qs.push('q='           + encodeURIComponent(params.q));
    if (params.page)        qs.push('page='        + params.page);
    if (params.limit)       qs.push('limit='       + params.limit);
  }
  return apiGet('/flp-case-studies' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiFlpCaseStudyDetail(id)        { return apiGet('/flp-case-studies/' + id); }
function apiFlpCaseStudyCreate(data)      { return apiPost('/flp-case-studies', data); }
function apiFlpCaseStudyUpdate(id, data)  { return apiPut('/flp-case-studies/' + id, data); }
function apiFlpCaseStudyDelete(id)        { return apiDelete('/flp-case-studies/' + id); }
function apiFlpCaseStudyUploadPhoto(id, file) {
  var fd = new FormData(); fd.append('file', file);
  return apiUpload('/flp-case-studies/' + id + '/photo', fd);
}
function apiFlpCaseStudyUploadAttachment(id, file) {
  var fd = new FormData(); fd.append('file', file);
  return apiUpload('/flp-case-studies/' + id + '/attachment', fd);
}

// 2026-06-01: MGJ Leader Action Log feature retired. All wrappers
// removed; the backend route is unregistered and the page divs/JS
// handlers are gone from app.js + index.html.

// ---- Azad Kishori (AK) ----
function apiAkList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch_id) qs.push('batch_id=' + params.batch_id);
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.date_from) qs.push('date_from=' + params.date_from);
    if (params.date_to) qs.push('date_to=' + params.date_to);
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
    // 2026-06-04: silent-drop bug fix — loadAkListData has been setting
    // p.include_dropout = true since 2026-05-30 expecting the backend to
    // return Active + Dropout, but the param was never forwarded by this
    // wrapper. Net effect: AK List showed only Active leaders (32 of 40
    // on stage). Dashboard counted Dropouts; List didn't. Same bug as
    // task #357 fixed for apiMgjList.
    if (params.include_dropout) qs.push('include_dropout=' + encodeURIComponent(params.include_dropout));
  }
  return apiGet('/ak' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkDetail(id) { return apiGet('/ak/' + id); }
function apiCreateAk(data) { return apiPost('/ak', data); }
function apiUpdateAk(id, data) { return apiPut('/ak/' + id, data); }
function apiDeleteAk(id) { return apiDelete('/ak/' + id); }
function apiAkWalkout(id, data) { return apiPost('/ak/' + id + '/walkout', data); }
function apiAkUploadPhoto(id, file) {
  var fd = new FormData(); fd.append('file', file);
  var headers = {}; if (authToken) headers['Authorization'] = 'Bearer ' + authToken;
  return fetch(API_BASE + '/ak/' + id + '/photo', { method: 'POST', headers: headers, body: fd }).then(function(r) { return r.json(); });
}

// AK Geo
function apiAkGeoStates() { return apiGet('/ak/geo/states'); }
function apiAkGeoCentres(stateCode) { return apiGet('/ak/geo/centres?state_code=' + encodeURIComponent(stateCode)); }

// AK Training
function apiAkTrainingList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch_id) qs.push('batch_id=' + params.batch_id);
    if (params.category) qs.push('category=' + encodeURIComponent(params.category));
    if (params.training_date) qs.push('training_date=' + params.training_date);
    if (params.topic_name) qs.push('topic_name=' + encodeURIComponent(params.topic_name));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/ak-training' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkTrainingDetail(id) { return apiGet('/ak-training/' + id); }
function apiCreateAkTraining(data) { return apiPost('/ak-training', data); }
function apiUpdateAkTraining(id, data) { return apiPut('/ak-training/' + id, data); }
function apiDeleteAkTraining(id) { return apiDelete('/ak-training/' + id); }
function apiAkTrainingEligible(id) { return apiGet('/ak-training/' + id + '/eligible-leaders'); }
function apiAkTrainingAssign(id, leaderIds) { return apiPost('/ak-training/' + id + '/participants', { leader_ids: leaderIds }); }
function apiAkTrainingAttendance(id, attendances) { return apiPut('/ak-training/' + id + '/attendance', { attendances: attendances }); }
function apiAkTrainingImages(id) { return apiGet('/ak-training/' + id + '/images'); }
function apiAkTrainingUploadImage(id, file) {
  var fd = new FormData(); fd.append('file', file);
  var headers = {}; if (authToken) headers['Authorization'] = 'Bearer ' + authToken;
  return fetch(API_BASE + '/ak-training/' + id + '/images', { method: 'POST', headers: headers, body: fd }).then(function(r) { return r.json(); });
}
function apiAkTrainingDeleteImage(imgId) { return apiDelete('/ak-training/images/' + imgId); }

// AK Batches
function apiAkBatchList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/ak-batches' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkBatchDetail(id) { return apiGet('/ak-batches/' + id); }
function apiCreateAkBatch(data) { return apiPost('/ak-batches', data); }
function apiUpdateAkBatch(id, data) { return apiPut('/ak-batches/' + id, data); }
function apiDeleteAkBatch(id) { return apiDelete('/ak-batches/' + id); }
function apiAkBatchUnallocated(id) { return apiGet('/ak-batches/' + id + '/unallocated'); }
function apiAkBatchAllocate(id, leaderIds) { return apiPost('/ak-batches/' + id + '/allocate', { leader_ids: leaderIds }); }

// AK Adda
function apiAkAddaList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch_id) qs.push('batch_id=' + params.batch_id);
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/ak-adda' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkAddaDetail(id) { return apiGet('/ak-adda/' + id); }
function apiCreateAkAdda(data) { return apiPost('/ak-adda', data); }
function apiUpdateAkAdda(id, data) { return apiPut('/ak-adda/' + id, data); }
function apiDeleteAkAdda(id) { return apiDelete('/ak-adda/' + id); }
function apiAkAddaLeaders(centreCode, stateCode, batchId, includeLeaderIds) {
  // 2026-05-30: Extended to accept an optional batchId so the multi-select
  // Leader picker in the Adda Add-Details modal can scope tightly to the
  // adda's batch.
  // 2026-06-04: Added includeLeaderIds (array of ints) so the Edit Adda
  // form can keep showing the Adda's own currently-linked leaders even
  // though the "one Adda per leader" exclusion would otherwise hide them.
  var qs = [];
  if (batchId) qs.push('batch_id=' + encodeURIComponent(batchId));
  if (centreCode) qs.push('centre_code=' + encodeURIComponent(centreCode));
  else if (stateCode) qs.push('state_code=' + encodeURIComponent(stateCode));
  if (includeLeaderIds && includeLeaderIds.length) {
    qs.push('include_leader_ids=' + encodeURIComponent(includeLeaderIds.join(',')));
  }
  return apiGet('/ak-adda/leaders-for-adda' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkAddaDetails(id) { return apiGet('/ak-adda/' + id + '/details'); }
function apiAddAkAddaDetail(id, data) { return apiPost('/ak-adda/' + id + '/details', data); }
function apiDeleteAkAddaDetail(detailId) { return apiDelete('/ak-adda/details/' + detailId); }

// AK Alumni
function apiAkAlumniList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.type_of_alumni) qs.push('type_of_alumni=' + encodeURIComponent(params.type_of_alumni));
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/ak-alumni' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkAlumniDetail(id) { return apiGet('/ak-alumni/' + id); }
function apiCreateAkAlumni(data) { return apiPost('/ak-alumni', data); }
function apiUpdateAkAlumni(id, data) { return apiPut('/ak-alumni/' + id, data); }
function apiDeleteAkAlumni(id) { return apiDelete('/ak-alumni/' + id); }
function apiAkAlumniTracking(id) { return apiGet('/ak-alumni/' + id + '/tracking'); }
// 2026-06-01 (v2): per-field inline edit endpoint for the 4 "living"
// Alumni fields (Marital Status, Address, Monthly Income, Phone Number)
// — used by the pencil-edit cells on the Alumni View page. body shape:
// { field: 'marital_status' | 'address' | 'monthly_income' | 'mobile',
//   value: <string|number|null> }
function apiAkAlumniInlineEdit(id, data) { return apiPatch('/ak-alumni/' + id + '/inline-field', data); }
function apiAddAkAlumniTracking(id, data) { return apiPost('/ak-alumni/' + id + '/tracking', data); }
function apiDeleteAkAlumniTracking(trackingId) { return apiDelete('/ak-alumni/tracking/' + trackingId); }

// ===== AAG (Azad Alumni Group) — paid membership =====
function apiAagList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch) qs.push('batch=' + encodeURIComponent(params.batch));
    if (params.type_of_alumni) qs.push('type_of_alumni=' + encodeURIComponent(params.type_of_alumni));
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/ak-aag' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAagEligibleAlumni(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch) qs.push('batch=' + encodeURIComponent(params.batch));
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/ak-aag/eligible-alumni' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAagDetail(id)        { return apiGet('/ak-aag/' + id); }
function apiAagRegister(data)    { return apiPost('/ak-aag/register', data); }
function apiAagUpdate(id, data)  { return apiPut('/ak-aag/' + id, data); }
function apiAagPay(id, data)     { return apiPost('/ak-aag/' + id + '/pay', data); }
function apiAagDelete(id)        { return apiDelete('/ak-aag/' + id); }

// ===== AK ALAP (Accelerator Leadership) =====
// Sub-module under AK programme. Routes live at /api/ak/alap on the
// backend. The router is registered before the generic /api/ak/{id}
// route so the path "alap" doesn't get parsed as a leader id.
function apiAkAlapList(params) {
  var qs = [];
  if (params) {
    if (params.batch_id)    qs.push('batch_id=' + params.batch_id);
    if (params.name)        qs.push('name=' + encodeURIComponent(params.name));
    if (params.status)      qs.push('status=' + encodeURIComponent(params.status));
    if (params.state_code)  qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.page)        qs.push('page=' + params.page);
    if (params.limit)       qs.push('limit=' + params.limit);
  }
  return apiGet('/ak/alap' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkAlapDetail(id)            { return apiGet('/ak/alap/' + id); }
function apiCreateAkAlap(data)          { return apiPost('/ak/alap', data); }
function apiUpdateAkAlap(id, data)      { return apiPut('/ak/alap/' + id, data); }
function apiDeleteAkAlap(id)            { return apiDelete('/ak/alap/' + id); }
function apiAddAkAlapInternship(id, d)  { return apiPost('/ak/alap/' + id + '/internship', d); }
function apiAddAkAlapEmployment(id, d)  { return apiPost('/ak/alap/' + id + '/employment', d); }

// ===== AK ALAP Training =====
// Trainings tied to ALAP cohorts. Backend at /api/ak/alap-training.
function apiAkAlapTrList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.phase)      qs.push('phase=' + encodeURIComponent(params.phase));
    if (params.month)      qs.push('month=' + encodeURIComponent(params.month));
    // date_from / date_to are legacy params kept for back-compat but the
    // form no longer captures Start/End dates after the May-2026 change.
    if (params.date_from)  qs.push('date_from=' + encodeURIComponent(params.date_from));
    if (params.date_to)    qs.push('date_to=' + encodeURIComponent(params.date_to));
    if (params.page)       qs.push('page=' + params.page);
    if (params.limit)      qs.push('limit=' + params.limit);
  }
  return apiGet('/ak/alap-training' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkAlapTrDetail(id)            { return apiGet('/ak/alap-training/' + id); }
function apiCreateAkAlapTr(data)          { return apiPost('/ak/alap-training', data); }
function apiUpdateAkAlapTr(id, data)      { return apiPut('/ak/alap-training/' + id, data); }
function apiDeleteAkAlapTr(id)            { return apiDelete('/ak/alap-training/' + id); }
function apiAkAlapTrAssignments(id)       { return apiGet('/ak/alap-training/' + id + '/assignments'); }
function apiAkAlapTrSetAssignments(id, alap_ids) {
  return apiPut('/ak/alap-training/' + id + '/assignments', { alap_ids: alap_ids });
}
function apiAkAlapTrAttendance(id, subtype, month) {
  var qs = [];
  if (subtype) qs.push('training_subtype=' + encodeURIComponent(subtype));
  if (month)   qs.push('attendance_month=' + encodeURIComponent(month));
  return apiGet('/ak/alap-training/' + id + '/attendance' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkAlapTrSaveAttendance(id, body) {
  return apiPost('/ak/alap-training/' + id + '/attendance', body);
}

// AK ALAP CRC
function apiAkAlapCrcList(params) {
  var qs = [];
  if (params) {
    if (params.month)   qs.push('month=' + encodeURIComponent(params.month));
    if (params.alap_id) qs.push('alap_id=' + params.alap_id);
    if (params.topic)   qs.push('topic=' + encodeURIComponent(params.topic));
    if (params.page)    qs.push('page=' + params.page);
    if (params.limit)   qs.push('limit=' + params.limit);
  }
  return apiGet('/ak/alap-crc' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkAlapCrcDetail(id)       { return apiGet('/ak/alap-crc/' + id); }
function apiCreateAkAlapCrc(data)     { return apiPost('/ak/alap-crc', data); }
function apiUpdateAkAlapCrc(id, data) { return apiPut('/ak/alap-crc/' + id, data); }
function apiDeleteAkAlapCrc(id)       { return apiDelete('/ak/alap-crc/' + id); }

// AK ALAP Activity Mapping
function apiAkAlapActivityMappingGet(alap_id, month) {
  return apiGet('/ak/alap-activity-mapping?alap_id=' + alap_id + '&month=' + encodeURIComponent(month));
}
function apiAkAlapActivityMappingSave(payload) {
  return apiPost('/ak/alap-activity-mapping', payload);
}

// AK ALAP Cohorts
function apiAkAlapCohortList(params) {
  var qs = [];
  if (params) {
    if (params.group_name) qs.push('group_name=' + encodeURIComponent(params.group_name));
    if (params.name)       qs.push('name=' + encodeURIComponent(params.name));
    if (params.page)       qs.push('page=' + params.page);
    if (params.limit)      qs.push('limit=' + params.limit);
  }
  return apiGet('/ak/alap-cohorts' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkAlapCohortDetail(id)       { return apiGet('/ak/alap-cohorts/' + id); }
function apiCreateAkAlapCohort(data)     { return apiPost('/ak/alap-cohorts', data); }
function apiUpdateAkAlapCohort(id, data) { return apiPut('/ak/alap-cohorts/' + id, data); }
function apiDeleteAkAlapCohort(id)       { return apiDelete('/ak/alap-cohorts/' + id); }

// AK Mentor Log
function apiAkMentorLogList(params) {
  var qs = [];
  if (params) {
    if (params.mentor_name) qs.push('mentor_name=' + encodeURIComponent(params.mentor_name));
    if (params.alap_id)     qs.push('alap_id=' + params.alap_id);
    if (params.date_from)   qs.push('date_from=' + encodeURIComponent(params.date_from));
    if (params.date_to)     qs.push('date_to=' + encodeURIComponent(params.date_to));
    if (params.page)        qs.push('page=' + params.page);
    if (params.limit)       qs.push('limit=' + params.limit);
  }
  return apiGet('/ak/mentor-log' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiAkMentorLogDetail(id)       { return apiGet('/ak/mentor-log/' + id); }
function apiCreateAkMentorLog(data)     { return apiPost('/ak/mentor-log', data); }
function apiUpdateAkMentorLog(id, data) { return apiPut('/ak/mentor-log/' + id, data); }
function apiDeleteAkMentorLog(id)       { return apiDelete('/ak/mentor-log/' + id); }

// AK Assessments
function apiAkAssessmentList(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.assessment_type) qs.push('assessment_type=' + encodeURIComponent(params.assessment_type));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.leader_name) qs.push('leader_name=' + encodeURIComponent(params.leader_name));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/ak-assessments' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiCreateAkAssessment(data) { return apiPost('/ak-assessments', data); }
function apiAkAssessmentDetail(id) { return apiGet('/ak-assessments/' + id); }

// MGJ Assessments (2026-05-27). Same endpoint shape as AK but member-scoped.
function apiMgjAssessmentList(params) {
  var qs = [];
  if (params) {
    if (params.state_code)    qs.push('state_code='    + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.centre_code)   qs.push('centre_code='   + encodeURIComponent(params.centre_code));
    if (params.assessment_type) qs.push('assessment_type=' + encodeURIComponent(params.assessment_type));
    if (params.status)        qs.push('status='        + encodeURIComponent(params.status));
    if (params.member_name)   qs.push('member_name='   + encodeURIComponent(params.member_name));
    if (params.page)          qs.push('page=' + params.page);
    if (params.limit)         qs.push('limit=' + params.limit);
  }
  return apiGet('/mgj-assessments' + (qs.length ? '?' + qs.join('&') : ''));
}
// Grouped variant — one row per member with latest baseline/midline/endline
// joined. Used by the list page to render an AK-style one-row-per-member view.
function apiMgjAssessmentGrouped(params) {
  var qs = [];
  if (params) {
    if (params.state_code)    qs.push('state_code='    + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.centre_code)   qs.push('centre_code='   + encodeURIComponent(params.centre_code));
    if (params.assessment_type) qs.push('assessment_type=' + encodeURIComponent(params.assessment_type));
    if (params.status)        qs.push('status='        + encodeURIComponent(params.status));
    if (params.member_name)   qs.push('member_name='   + encodeURIComponent(params.member_name));
    if (params.page)          qs.push('page=' + params.page);
    if (params.limit)         qs.push('limit=' + params.limit);
  }
  return apiGet('/mgj-assessments/list/grouped' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiMgjAssessmentEligible(params) {
  var qs = ['assessment_type=' + encodeURIComponent(params.assessment_type)];
  if (params.state_code)  qs.push('state_code='  + encodeURIComponent(params.state_code));
  if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
  if (params.name)        qs.push('name='        + encodeURIComponent(params.name));
  if (params.limit)       qs.push('limit=' + params.limit);
  return apiGet('/mgj-assessments/eligible-members?' + qs.join('&'));
}
function apiMgjAssessmentStart(memberId, assessmentType) {
  return apiPost('/mgj-assessments/start', { member_id: memberId, assessment_type: assessmentType });
}
function apiMgjAssessmentDetail(id) { return apiGet('/mgj-assessments/' + id); }
function apiMgjAssessmentSubmit(id) { return apiPost('/mgj-assessments/' + id + '/submit', {}); }
function apiMgjAssessmentDelete(id) { return apiDelete('/mgj-assessments/' + id); }
// 2026-06-01: 3-stage comparison endpoint — returns the member +
// whichever of {Baseline, Midline, Endline} are on file. Drives the
// MGJ Assessment Comparison page (mirrors AK's pattern but in a
// single round-trip).
function apiMgjAssessmentComparison(memberId) {
  return apiGet('/mgj-assessments/comparison?member_id=' + encodeURIComponent(memberId));
}

// ---- Programs ----
function apiGetPrograms() { return apiGet('/programs'); }
function apiGetUserPrograms(userId) { return apiGet('/programs/user/' + userId); }
function apiAssignPrograms(userId, programCodes) { return apiPost('/programs/assign', { user_id: userId, program_codes: programCodes }); }

// ---- State Lead Dashboard ----
function _slDashQs(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.district_code) qs.push('district_code=' + encodeURIComponent(params.district_code));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.month) qs.push('month=' + encodeURIComponent(params.month));
  }
  return qs.length ? '?' + qs.join('&') : '';
}
function apiStateDashSummary(params) { return apiGet('/state-dashboard/summary' + _slDashQs(params)); }
function apiStateDashAge(params) { return apiGet('/state-dashboard/age-distribution' + _slDashQs(params)); }
function apiStateDashSurvey(params) { return apiGet('/state-dashboard/survey-summary' + _slDashQs(params)); }
function apiStateDashTraining(params) { return apiGet('/state-dashboard/training-progress' + _slDashQs(params)); }
function apiStateDashTargetAch(params) { return apiGet('/state-dashboard/target-vs-achievement' + _slDashQs(params)); }
function apiStateDashMapPoints(params) { return apiGet('/state-dashboard/survey-map-points' + _slDashQs(params)); }

// ===== INTERNSHIPS — Organisations =====
function apiOrganizations(params) {
  var qs = [];
  if (params) {
    if (params.name) qs.push('name=' + encodeURIComponent(params.name));
    if (params.org_type) qs.push('org_type=' + encodeURIComponent(params.org_type));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/organizations' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiOrganizationDetail(id) { return apiGet('/organizations/' + id); }
function apiCreateOrganization(data) { return apiPost('/organizations', data); }
function apiUpdateOrganization(id, data) { return apiPut('/organizations/' + id, data); }
function apiDeleteOrganization(id) { return apiDelete('/organizations/' + id); }

// ===== INTERNSHIPS — Assignments =====
function apiInternships(params) {
  var qs = [];
  if (params) {
    if (params.state_code) qs.push('state_code=' + encodeURIComponent(params.state_code));
    if (params.batch_id) qs.push('batch_id=' + params.batch_id);
    if (params.flp_name) qs.push('flp_name=' + encodeURIComponent(params.flp_name));
    if (params.organization_id) qs.push('organization_id=' + params.organization_id);
    if (params.date_from) qs.push('date_from=' + params.date_from);
    if (params.date_to) qs.push('date_to=' + params.date_to);
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/internships' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiInternshipDetail(id) { return apiGet('/internships/' + id); }
function apiCreateInternship(data) { return apiPost('/internships', data); }
function apiUpdateInternship(id, data) { return apiPut('/internships/' + id, data); }
function apiDeleteInternship(id) { return apiDelete('/internships/' + id); }

// ===== INTERNSHIPS — Reports =====
function apiInternshipReports(assignmentId) { return apiGet('/internships/' + assignmentId + '/reports'); }
function apiCreateInternshipReport(assignmentId, data) { return apiPost('/internships/' + assignmentId + '/reports', data); }
function apiUploadInternshipReportFile(reportId, kind, file) {
  var fd = new FormData();
  fd.append('file', file);
  return apiUpload('/internships/reports/' + reportId + '/files?kind=' + encodeURIComponent(kind), fd);
}

// ===== SANGINI (AK) =====
function apiSanginiList(params) {
  var qs = [];
  if (params) {
    if (params.month) qs.push('month=' + encodeURIComponent(params.month));
    if (params.sangini_name) qs.push('sangini_name=' + encodeURIComponent(params.sangini_name));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/sangini' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiSanginiDetail(id) { return apiGet('/sangini/' + id); }
function apiSanginiNames() { return apiGet('/sangini/names'); }
function apiSanginiAddaProfiles() { return apiGet('/sangini/adda-profiles'); }
function apiSanginiMonths() { return apiGet('/sangini/months'); }
function apiCreateSangini(data) { return apiPost('/sangini', data); }
function apiUpdateSangini(id, data) { return apiPut('/sangini/' + id, data); }
function apiDeleteSangini(id) { return apiDelete('/sangini/' + id); }

// ===== MGJ Overall Activities =====
function apiMgjMonthlyList(params) {
  var qs = [];
  if (params) {
    if (params.year) qs.push('year=' + encodeURIComponent(params.year));
    if (params.month) qs.push('month=' + encodeURIComponent(params.month));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch_id) qs.push('batch_id=' + params.batch_id);
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/mgj-monthly' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiMgjMonthlyDetail(id) { return apiGet('/mgj-monthly/' + id); }
function apiCreateMgjMonthly(data) { return apiPost('/mgj-monthly', data); }
function apiUpdateMgjMonthly(id, data) { return apiPut('/mgj-monthly/' + id, data); }
function apiDeleteMgjMonthly(id) { return apiDelete('/mgj-monthly/' + id); }
function apiMgjMonthlyPivot(params) {
  var qs = [];
  if (params) {
    if (params.year) qs.push('year=' + encodeURIComponent(params.year));
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.batch_id) qs.push('batch_id=' + params.batch_id);
  }
  return apiGet('/mgj-monthly/pivot' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiMgjMonthlyAutocompleteCampaigns() { return apiGet('/mgj-monthly/autocomplete/campaigns'); }
function apiMgjMonthlyAutocompleteTopics(kind) { return apiGet('/mgj-monthly/autocomplete/topics' + (kind ? '?kind=' + encodeURIComponent(kind) : '')); }

// ===== MGJ Campaign Images (per-campaign attachments) =====
function apiMgjListCampaignImages(campaignId)   { return apiGet('/mgj-monthly/campaigns/' + campaignId + '/images'); }
function apiMgjUploadCampaignImage(campaignId, file) {
  var fd = new FormData(); fd.append('file', file);
  return apiUpload('/mgj-monthly/campaigns/' + campaignId + '/images', fd);
}
function apiMgjDeleteCampaignImage(imgId)       { return apiDelete('/mgj-monthly/campaigns/images/' + imgId); }

// ===== MGJ Pakhwada =====
function apiMgjPakhwadaList(params) {
  var qs = [];
  if (params) {
    if (params.session_type) qs.push('session_type=' + encodeURIComponent(params.session_type));
    if (params.month) qs.push('month=' + params.month);
    if (params.year) qs.push('year=' + params.year);
    if (params.centre_code) qs.push('centre_code=' + encodeURIComponent(params.centre_code));
    if (params.date_from) qs.push('date_from=' + params.date_from);
    if (params.date_to) qs.push('date_to=' + params.date_to);
    if (params.topic) qs.push('topic=' + encodeURIComponent(params.topic));
    if (params.status) qs.push('status=' + encodeURIComponent(params.status));
    if (params.page) qs.push('page=' + params.page);
    if (params.limit) qs.push('limit=' + params.limit);
  }
  return apiGet('/mgj-pakhwada' + (qs.length ? '?' + qs.join('&') : ''));
}
function apiMgjPakhwadaDetail(id) { return apiGet('/mgj-pakhwada/' + id); }
function apiCreateMgjPakhwada(data) { return apiPost('/mgj-pakhwada', data); }
function apiUpdateMgjPakhwada(id, data) { return apiPut('/mgj-pakhwada/' + id, data); }
function apiDeleteMgjPakhwada(id) { return apiDelete('/mgj-pakhwada/' + id); }
function apiMgjPakhwadaMembers(id) { return apiGet('/mgj-pakhwada/' + id + '/members'); }
function apiSubmitMgjPakhwadaAttendance(id, data) { return apiPost('/mgj-pakhwada/' + id + '/attendance', data); }
function apiMgjPakhwadaTopics() { return apiGet('/mgj-pakhwada/autocomplete/topics'); }

// ===== MGJ Master (State/District/Centre/Area/Batch) — isolated from FLP =====
function _qs(p) {
  if (!p) return '';
  var qs = [];
  for (var k in p) {
    if (p[k] !== undefined && p[k] !== null && p[k] !== '') qs.push(k + '=' + encodeURIComponent(p[k]));
  }
  return qs.length ? '?' + qs.join('&') : '';
}
// States
function apiMgjMStates(p) { return apiGet('/mgj-master/states' + _qs(p)); }
function apiMgjMStatesDropdown() { return apiGet('/mgj-master/dropdown/states'); }
function apiMgjMCreateState(d) { return apiPost('/mgj-master/states', d); }
function apiMgjMUpdateState(code, d) { return apiPut('/mgj-master/states/' + encodeURIComponent(code), d); }
function apiMgjMDeleteState(code) { return apiDelete('/mgj-master/states/' + encodeURIComponent(code)); }
// Districts
function apiMgjMDistricts(p) { return apiGet('/mgj-master/districts' + _qs(p)); }
function apiMgjMDistrictsDropdown(p) { return apiGet('/mgj-master/dropdown/districts' + _qs(p)); }
function apiMgjMCreateDistrict(d) { return apiPost('/mgj-master/districts', d); }
function apiMgjMUpdateDistrict(code, d) { return apiPut('/mgj-master/districts/' + encodeURIComponent(code), d); }
function apiMgjMDeleteDistrict(code) { return apiDelete('/mgj-master/districts/' + encodeURIComponent(code)); }
// Centres
function apiMgjMCentres(p) { return apiGet('/mgj-master/centres' + _qs(p)); }
function apiMgjMCentresDropdown(p) { return apiGet('/mgj-master/dropdown/centres' + _qs(p)); }
function apiMgjMCreateCentre(d) { return apiPost('/mgj-master/centres', d); }
function apiMgjMUpdateCentre(code, d) { return apiPut('/mgj-master/centres/' + encodeURIComponent(code), d); }
function apiMgjMDeleteCentre(code) { return apiDelete('/mgj-master/centres/' + encodeURIComponent(code)); }
// Areas
function apiMgjMAreas(p) { return apiGet('/mgj-master/areas' + _qs(p)); }
function apiMgjMAreasDropdown(p) { return apiGet('/mgj-master/dropdown/areas' + _qs(p)); }
function apiMgjMCreateArea(d) { return apiPost('/mgj-master/areas', d); }
function apiMgjMUpdateArea(code, d) { return apiPut('/mgj-master/areas/' + encodeURIComponent(code), d); }
function apiMgjMDeleteArea(code) { return apiDelete('/mgj-master/areas/' + encodeURIComponent(code)); }
// Batches
function apiMgjMBatches(p) { return apiGet('/mgj-master/batches' + _qs(p)); }
function apiMgjMBatchesDropdown(p) { return apiGet('/mgj-master/dropdown/batches' + _qs(p)); }
function apiMgjMCreateBatch(d) { return apiPost('/mgj-master/batches', d); }
function apiMgjMUpdateBatch(id, d) { return apiPut('/mgj-master/batches/' + id, d); }
function apiMgjMDeleteBatch(id) { return apiDelete('/mgj-master/batches/' + id); }
// 2026-06-09: MGJ Leader Batch Management — separate master from
// Batch Management above. Powers leader_batch_id on mgj_leaders +
// mgj_leader_trainings. Same CRUD shape as batches.
function apiMgjMLeaderBatches(p)         { return apiGet('/mgj-master/leader-batches' + _qs(p)); }
function apiMgjMLeaderBatchesDropdown(p) { return apiGet('/mgj-master/dropdown/leader-batches' + _qs(p)); }
function apiMgjMCreateLeaderBatch(d)     { return apiPost('/mgj-master/leader-batches', d); }
function apiMgjMUpdateLeaderBatch(id, d) { return apiPut('/mgj-master/leader-batches/' + id, d); }
function apiMgjMDeleteLeaderBatch(id)    { return apiDelete('/mgj-master/leader-batches/' + id); }
// Groups — mirror of Batches but with an Area dimension. One area can have
// multiple groups; group dropdowns accept state/centre/area as filters.
function apiMgjMGroups(p) { return apiGet('/mgj-master/groups' + _qs(p)); }
function apiMgjMGroupsDropdown(p) { return apiGet('/mgj-master/dropdown/groups' + _qs(p)); }
function apiMgjMCreateGroup(d) { return apiPost('/mgj-master/groups', d); }
function apiMgjMUpdateGroup(id, d) { return apiPut('/mgj-master/groups/' + id, d); }
function apiMgjMDeleteGroup(id) { return apiDelete('/mgj-master/groups/' + id); }

// ====================================================================
// AK Master API helpers — hit /api/ak-master/* (independent of MGJ / FLP)
// ====================================================================
// States
function apiAkMStates(p) { return apiGet('/ak-master/states' + _qs(p)); }
function apiAkMStatesDropdown() { return apiGet('/ak-master/dropdown/states'); }
function apiAkMCreateState(d) { return apiPost('/ak-master/states', d); }
function apiAkMUpdateState(code, d) { return apiPut('/ak-master/states/' + encodeURIComponent(code), d); }
function apiAkMDeleteState(code) { return apiDelete('/ak-master/states/' + encodeURIComponent(code)); }
// Districts
function apiAkMDistricts(p) { return apiGet('/ak-master/districts' + _qs(p)); }
function apiAkMDistrictsDropdown(p) { return apiGet('/ak-master/dropdown/districts' + _qs(p)); }
function apiAkMCreateDistrict(d) { return apiPost('/ak-master/districts', d); }
function apiAkMUpdateDistrict(code, d) { return apiPut('/ak-master/districts/' + encodeURIComponent(code), d); }
function apiAkMDeleteDistrict(code) { return apiDelete('/ak-master/districts/' + encodeURIComponent(code)); }
// Centres
function apiAkMCentres(p) { return apiGet('/ak-master/centres' + _qs(p)); }
function apiAkMCentresDropdown(p) { return apiGet('/ak-master/dropdown/centres' + _qs(p)); }
function apiAkMCreateCentre(d) { return apiPost('/ak-master/centres', d); }
function apiAkMUpdateCentre(code, d) { return apiPut('/ak-master/centres/' + encodeURIComponent(code), d); }
function apiAkMDeleteCentre(code) { return apiDelete('/ak-master/centres/' + encodeURIComponent(code)); }
// Areas
function apiAkMAreas(p) { return apiGet('/ak-master/areas' + _qs(p)); }
function apiAkMAreasDropdown(p) { return apiGet('/ak-master/dropdown/areas' + _qs(p)); }
function apiAkMCreateArea(d) { return apiPost('/ak-master/areas', d); }
function apiAkMUpdateArea(code, d) { return apiPut('/ak-master/areas/' + encodeURIComponent(code), d); }
function apiAkMDeleteArea(code) { return apiDelete('/ak-master/areas/' + encodeURIComponent(code)); }

// AAG AGM (under AK Alumni)
function apiAkAgmList(p) { return apiGet('/ak/alumni-agm' + _qs(p)); }
function apiAkAgmDetail(id) { return apiGet('/ak/alumni-agm/' + id); }
function apiCreateAkAgm(d) { return apiPost('/ak/alumni-agm', d); }
function apiUpdateAkAgm(id, d) { return apiPut('/ak/alumni-agm/' + id, d); }
function apiDeleteAkAgm(id) { return apiDelete('/ak/alumni-agm/' + id); }

// MGJ Dashboard
function apiMgjDashboardStats(p)   { return apiGet('/mgj-dashboard/stats'  + _qs(p)); }
function apiMgjDashboardCharts(p)  { return apiGet('/mgj-dashboard/charts' + _qs(p)); }
function apiMgjDashboardMis(p)     { return apiGet('/mgj-dashboard/mis'    + _qs(p)); }
function apiMgjDashboardDrill(p)   { return apiGet('/mgj-dashboard/drill-down/members' + _qs(p)); }

// AK Dashboard
function apiAkDashboardStats(p)    { return apiGet('/ak-dashboard/stats'   + _qs(p)); }
function apiAkDashboardCharts(p)   { return apiGet('/ak-dashboard/charts'  + _qs(p)); }

// ALAP Performance (over Activity Mapping data)
function apiAlapPerfOverall(p)     { return apiGet('/ak/alap-performance/overall'    + _qs(p)); }
function apiAlapPerfIndividual(p)  { return apiGet('/ak/alap-performance/individual' + _qs(p)); }
// Unified FLP-style endpoint — returns summary + columns + categories + rows
// (each row carries its raw category JSONB for the expandable detail).
function apiAlapPerformance(p)     { return apiGet('/ak/alap-performance'             + _qs(p)); }