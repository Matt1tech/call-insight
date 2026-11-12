// Call Insight dashboard. All text goes through h() / textContent: transcripts are untrusted.

const FILTER_DEFS = [
  { key: "language", label: "Language" },
  { key: "sentiment", label: "Sentiment" },
  { key: "intent", label: "Primary intent" },
  { key: "resolution", label: "Resolution" },
  { key: "risk", label: "Risk", title: "Highest of escalation risk and repeat-contact risk" },
];
const KIND_LABELS = {
  unsupported_claim: "Unsupported claims",
  unverified_statement: "Unverified statements",
  unknown_cause: "Unknown causes",
  missing_programme_info: "Missing programme information",
  needs_verification: "Needs verification",
};
const RISK_ORDER = { High: 0, Medium: 1, Low: 2, Unknown: 3 };
const SERVER_CMD = "cd backend && uv run uvicorn app.main:app";

const state = { filters: Object.fromEntries(FILTER_DEFS.map((f) => [f.key, ""])), total: null };
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let renderToken = 0;

/* ---------- helpers ---------- */
function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style") el.setAttribute("style", v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
const $ = (sel, root = document) => root.querySelector(sel);

function resClass(status) { return status === "Resolved" ? "ok" : status === "Unresolved" ? "bad" : "unk"; }
function riskClass(level) { return level === "High" ? "bad" : level === "Medium" ? "warn" : level === "Low" ? "ok" : "unk"; }
function chip(text, cls = "") { return h("span", { class: `chip ${cls}`.trim() }, text); }
function firstSentence(s = "") { return (s.split(/(?<=[.!?])\s/)[0] || s).trim(); }
function fmtPct(n) { return Number.isInteger(n) ? String(n) : n.toFixed(1); }
function idLink(id) { return h("a", { href: `#/conversations/${encodeURIComponent(id)}` }, id); }
function idList(ids) {
  if (!ids || !ids.length) return h("p", { class: "muted small" }, "None.");
  return h("ul", { class: "idlist" }, ids.map((id) => h("li", {}, idLink(id))));
}
function list(items, emptyText) {
  if (!items || !items.length) return h("p", { class: "none muted small" }, emptyText);
  return h("ul", {}, items.map((i) => h("li", {}, i)));
}

function query() {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(state.filters)) if (v) p.set(k, v);
  const s = p.toString();
  return s ? `?${s}` : "";
}
async function api(path, { filtered = true } = {}) {
  const res = await fetch(`/api${path}${filtered ? query() : ""}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function setCount(shown, total) {
  if (total != null) state.total = total;
  const t = state.total ?? total ?? shown;
  $("#count").textContent = `Showing ${shown} of ${t}`;
}

/* ---------- shared view pieces ---------- */
function barList(items, colorFn = () => "") {
  const max = Math.max(1, ...items.map((i) => i.count));
  return h("ul", { class: "bars" }, items.map((i) =>
    h("li", {},
      h("span", {}, i.label),
      h("div", { class: "track", "aria-hidden": "true" },
        h("div", { class: `fill ${colorFn(i.label)}`, style: `width:${(i.count / max) * 100}%` })),
      h("span", { class: "n" }, i.count))));
}
const sentimentColor = (l) => ({ Positive: "ok", Negative: "bad", Neutral: "neutral", Unknown: "unk" }[l] || "");
const riskColor = (l) => riskClass(l);

function emptyPanel() {
  return h("div", { class: "panel-msg" },
    h("p", {}, "No conversations match these filters."),
    h("button", { class: "btn", type: "button", onclick: resetFilters }, "Reset filters"));
}
function errorPanel(err) {
  return h("div", { class: "panel-msg error", role: "alert" },
    h("p", {}, h("strong", {}, "Can't reach the API.")),
    h("p", {}, "Start the backend: ", h("code", {}, SERVER_CMD)),
    h("p", { class: "muted small" }, `Details: ${err && err.message ? err.message : err}`));
}

/* ---------- views ---------- */
async function viewOverview() {
  const d = await api("/analytics/overview");
  setCount(d.shown, d.total);
  if (!d.shown) return emptyPanel();
  const count = (s) => d.calls.filter((c) => c.resolution === s).length;
  
  const hero = h("section", { class: "hero" },
    h("span", { class: "big" }, d.shown),
    h("p", {}, d.shown === d.total
      ? `conversations analysed. ${count("Resolved")} resolved, ${count("Unresolved")} unresolved, ${count("Unknown")} where the outcome cannot be confirmed.`
      : `of ${d.total} conversations match the filters. ${count("Resolved")} resolved, ${count("Unresolved")} unresolved, ${count("Unknown")} unconfirmed.`));

  const shelf = h("section", { class: "shelf-wrap", "aria-labelledby": "shelf-h" },
    h("h2", { id: "shelf-h" }, "All calls"),
    h("p", { class: "muted" }, "Select a tag to open that call's full analysis."),
    h("div", { class: "shelf" }, d.calls.map((c, i) =>
      h("a", { class: "tag", href: `#/conversations/${encodeURIComponent(c.id)}`, style: `--i:${i}`,
        "aria-label": `${c.id}, ${c.intent}, ${c.resolution}, ${c.overall_risk} risk` },
        h("span", { class: `tag-band ${resClass(c.resolution)}` }, h("span", { class: "tag-id" }, c.id)),
        h("span", { class: "tag-body" },
          h("span", { class: "tag-intent" }, c.intent),
          h("span", { class: "tag-meta" }, c.language),
          h("span", { class: "tag-foot" },
            h("span", {}, c.resolution),
            h("span", { class: `risk-mark ${riskClass(c.overall_risk)}` }, h("i"), `${c.overall_risk} risk`)))))),
    h("div", { class: "shelf-key", "aria-hidden": "true" },
      h("span", {}, h("b", { class: "ok" }), "Resolved"),
      h("span", {}, h("b", { class: "bad" }), "Unresolved"),
      h("span", {}, h("b", { class: "unk" }), "Unknown, cannot be confirmed")));

  const block = (title, items, fn) => h("section", {}, h("h3", {}, title), barList(items, fn));
  const breakdowns = h("div", { class: "breakdowns" },
    block("Sentiment", d.sentiment, sentimentColor),
    block("Emotion", d.emotion, () => ""),
    block("Primary intent", d.intent, () => ""),
    block("Language", d.language, (l) => (l === "Unknown" ? "unk" : "")));
  return h("div", {}, hero, shelf, breakdowns);
}

async function viewResolution() {
  const d = await api("/analytics/resolution");
  setCount(d.shown, d.total);
  if (!d.shown) return emptyPanel();
  const segs = [
    ["Resolved", d.resolved, "ok"],
    ["Unresolved", d.unresolved, "bad"],
    ["Unknown", d.unknown, "unk"],
  ];
  const rate = fmtPct(d.resolution_rate);
  const defs = {
    Resolved: "Confirmed that the issue or enquiry is addressed.",
    Unresolved: "A material request remains open.",
    Unknown: "The outcome cannot be confirmed from the transcript.",
  };
  const cells = d.matrix.cells || {};
  const hasCall6 = Object.values(cells).some((ids) => ids.includes("CALL-006"));

  return h("div", {},
    h("section", {},
      h("h2", {}, "Resolution"),
      h("div", { class: "rate" },
        h("span", { class: "big" }, `${rate}%`),
        h("div", {},
          h("div", { class: "formula" }, `${d.formula} = ${rate}%`),
          h("p", { class: "muted small" }, "Resolution rate is Resolved divided by all analysed conversations. Unknown stays in the total and is never counted as resolved."))),
      h("div", { class: "seg", role: "img", "aria-label": `Resolved ${d.resolved}, Unresolved ${d.unresolved}, Unknown ${d.unknown}` },
        segs.filter(([, n]) => n > 0).map(([label, n, cls]) =>
          h("div", { class: cls, style: `flex:${n} 1 0` }, `${label} ${n}`))),
      h("p", { class: "muted small" }, "Grey = Unknown: the outcome cannot be confirmed.")),
    h("section", { class: "status-cols" }, segs.map(([label, n, cls]) =>
      h("div", {},
        h("h3", {}, chip(label, cls), h("span", { class: "num" }, n)),
        h("p", { class: "def" }, defs[label]),
        idList(d.by_status[label])))),
    h("section", {},
      h("h2", {}, "Resolution against sentiment"),
      h("div", { style: "overflow-x:auto" },
        h("table", { class: "matrix" },
          h("caption", {}, "Rows are resolution status; columns are the beneficiary's sentiment."),
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Resolution"), d.matrix.cols.map((c) => h("th", { scope: "col" }, c)))),
          h("tbody", {}, d.matrix.rows.map((r) =>
            h("tr", {}, h("th", { scope: "row" }, r), d.matrix.cols.map((c) => {
              const ids = cells[`${r}|${c}`] || [];
              return h("td", { class: ids.length ? "" : "empty" }, ids.length ? idList(ids) : "None");
            })))))),
      h("p", { class: "note" }, "Resolution is whether the request was closed. Sentiment is how the beneficiary felt. A call can be resolved without being satisfying, and a completed payment does not close a separate service complaint.",
        hasCall6 ? " For example, CALL-006: the balance problem was fixed, but the call stays Unresolved and Negative because the service complaint is still open." : "")));
}

async function viewRisks() {
  const d = await api("/analytics/risks");
  setCount(d.shown, d.total);
  if (!d.shown) return emptyPanel();
  const cases = [...d.cases].sort((a, b) =>
    (RISK_ORDER[a.overall_risk] ?? 9) - (RISK_ORDER[b.overall_risk] ?? 9) || a.id.localeCompare(b.id));
  const why = (reason, reasons, label) => h("details", {},
    h("summary", {}, "Why"),
    reason ? h("p", { class: "small" }, reason) : null,
    list(reasons, `No ${label} reasons recorded.`));
  const yn = (v) => chip(v === "Yes" ? "Escalate: Yes" : v === "No" ? "Escalate: No" : "Escalate: Unknown", v === "Yes" ? "bad" : v === "Unknown" ? "unk" : "");

  return h("div", {},
    h("h2", {}, "Escalation and risk"),
    h("div", { class: "stats" },
      h("div", { class: "stat" }, h("span", { class: "big" }, d.escalation_cases), h("span", { class: "lbl" }, "escalation cases")),
      h("div", { class: "stat" }, h("span", { class: "big" }, d.high_risk), h("span", { class: "lbl" }, "high-risk conversations"))),
    h("div", { class: "dists" },
      h("section", {}, h("h3", {}, "Escalation risk"), barList(d.escalation_risk, riskColor)),
      h("section", {}, h("h3", {}, "Repeat-contact risk"), barList(d.repeat_contact_risk, riskColor))),
    h("p", { class: "muted small" }, "Risk levels are qualitative indicators from the transcript, not predictions of what will happen. High-risk means escalation or repeat-contact risk is High."),
    h("div", { style: "overflow-x:auto" },
      h("table", { class: "cases" },
        h("thead", {}, h("tr", {}, ["Call", "Escalation", "Repeat contact", "Priority and team"].map((c) => h("th", { scope: "col" }, c)))),
        h("tbody", {}, cases.map((c) =>
          h("tr", {},
            h("td", { "data-label": "Call" }, h("div", { class: "stack" }, idLink(c.id), h("span", { class: "small muted" }, `${c.intent}, urgency ${c.urgency}`), chip(`${c.overall_risk} risk`, riskClass(c.overall_risk)))),
            h("td", { "data-label": "Escalation" }, h("div", { class: "stack" }, yn(c.escalation_required), chip(`${c.escalation_level} risk`, riskClass(c.escalation_level))), why(c.escalation_reason, c.escalation_reasons, "escalation")),
            h("td", { "data-label": "Repeat contact" }, h("div", { class: "stack" }, chip(`${c.repeat_level} risk`, riskClass(c.repeat_level))), why("", c.repeat_reasons, "repeat-contact")),
            h("td", { "data-label": "Priority and team" },
              chip(c.priority, c.priority === "Urgent" ? "warn" : c.priority === "High" ? "bad" : ""),
              h("span", { class: "team" }, c.team),
              h("details", {}, h("summary", {}, "Recommended action"), h("p", { class: "small" }, `Recommendation, not yet performed: ${c.next_best_action}`)))))))));
}

function highlight(text, quotes) {
  const ranges = [];
  for (const q of quotes) {
    const i = text.indexOf(q);
    if (i >= 0) ranges.push([i, i + q.length]);
  }
  if (!ranges.length) return [text];
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  const out = [];
  let pos = 0;
  for (const [s, e] of merged) {
    if (s > pos) out.push(text.slice(pos, s));
    out.push(h("mark", {}, text.slice(s, e)));
    pos = e;
  }
  if (pos < text.length) out.push(text.slice(pos));
  return out;
}

function gapItem(g, withCall = false) {
  return h("li", {},
    h("div", {}, withCall ? [idLink(g.call_id), " "] : null, chip(KIND_LABELS[g.kind] || g.kind), " ", g.statement),
    h("div", { class: "meta" }, `Said or reported by: ${g.attributed_to}. Verify with: ${g.verification}.`));
}

function conversationDetail(c, hiddenByFilters) {
  const cited = {};
  for (const e of c.evidence) (cited[e.turn] ||= []).push(e.quote);
  const turnEl = (t) => h("li", { id: `turn-${c.id}-${t.turn}`, class: `${t.speaker === "Agent" ? "agent" : "ben"}${cited[t.turn] ? " cited" : ""}` },
    h("span", { class: "t" }, t.turn),
    h("div", {}, h("span", { class: "who" }, `${t.speaker}${t.label !== t.speaker ? ` (${t.label})` : ""}`), h("span", {}, highlight(t.text, cited[t.turn] || []))));
  const jump = (turn) => {
    const el = document.getElementById(`turn-${c.id}-${turn}`);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 1600);
  };
  const r = c.resolution;
  const pair = (label, value, note) => h("div", {}, h("dt", {}, label), h("dd", {}, value, note ? h("small", {}, note) : null));
  const rc = c.root_cause;

  return h("article", { class: "detail", "aria-label": `${c.id} analysis` },
    hiddenByFilters ? h("p", { class: "hidden-note" }, "This call is hidden by the current filters. Reset filters to see it in the list.") : null,
    h("div", { class: "detail-head" },
      h("h2", {}, c.id),
      h("div", { class: "chips" }, chip(c.intent.value), chip(r.status, resClass(r.status)), chip(`${c.overall_risk} risk`, riskClass(c.overall_risk)), chip(`Confidence: ${c.confidence.level}`))),
    h("p", { class: "summary" }, c.summary),
    c.flags && c.flags.length ? h("div", { class: "chips" }, c.flags.map((f) => chip(f, "warn"))) : null,

    h("section", {}, h("h3", {}, "Classification"),
      h("dl", { class: "dl" },
        pair("Language", c.language.value, c.language.basis),
        pair("Primary intent", c.intent.value, c.intent.reason),
        pair("Sentiment", c.sentiment.sentiment, c.sentiment.reason),
        pair("Emotion", c.sentiment.emotion),
        pair("Conversation tone", c.sentiment.tone),
        pair("Urgency", r.urgency, r.urgency_reason),
        pair("Resolution", r.status, r.status_reason),
        pair("Escalation required", r.escalation_required, r.escalation_reason))),

    h("section", {}, h("h3", {}, "Supporting evidence"),
      h("div", { class: "evidence-grid" },
        h("ol", { class: "transcript", "aria-label": "Transcript" }, c.turns.map(turnEl)),
        h("div", {},
          h("p", { class: "muted small" }, "Select a quote to jump to its turn. Quotes keep their original language."),
          h("ul", { class: "ev-list" }, c.evidence.map((e) =>
            h("li", {}, h("button", { type: "button", onclick: () => jump(e.turn) },
              h("span", { class: "q" }, h("span", { class: "tt" }, e.turn), `"${e.quote}"`),
              h("span", { class: "s" }, e.supports)))))))),

    h("section", {}, h("h3", {}, "Root cause"),
      h("p", {}, h("strong", {}, "Likely cause: "), rc.likely_cause),
      h("div", { class: "rc-cols" },
        h("div", {}, h("h4", {}, "Observed facts"), list(rc.observed_facts, "None recorded.")),
        h("div", {}, h("h4", {}, "Assumptions"), list(rc.assumptions, "None made.")),
        h("div", { class: "missing" }, h("h4", {}, "Missing information"), list(rc.missing_information, "None identified.")))),

    h("section", {}, h("h3", {}, "Predictive analysis"),
      h("p", { class: "muted small" }, "Qualitative indicators based on this transcript, not guaranteed outcomes."),
      h("div", { class: "pred" },
        h("div", {}, h("h4", {}, "Escalation risk", chip(c.risk.escalation.level, riskClass(c.risk.escalation.level))), list(c.risk.escalation.reasons, "No reasons recorded.")),
        h("div", {}, h("h4", {}, "Repeat-contact risk", chip(c.risk.repeat_contact.level, riskClass(c.risk.repeat_contact.level))), list(c.risk.repeat_contact.reasons, "No reasons recorded.")))),

    h("section", {}, h("h3", {}, "Recommended action"),
      h("div", { class: "rec" },
        h("span", { class: "tagline" }, "Recommendation, not yet performed"),
        h("p", {}, c.action.next_best_action),
        h("dl", {},
          h("div", {}, h("dt", {}, "Responsible team"), h("dd", {}, c.action.team)),
          h("div", {}, h("dt", {}, "Priority"), h("dd", {}, chip(c.action.priority, c.action.priority === "Urgent" ? "warn" : c.action.priority === "High" ? "bad" : ""))),
          h("div", {}, h("dt", {}, "Check before closing"), h("dd", {}, list(c.action.verify_before_closing, "Nothing outstanding."))),
          h("div", {}, h("dt", {}, "Complete when"), h("dd", {}, c.action.completion_criteria))))),

    h("section", {}, h("h3", {}, "Knowledge gaps"),
      c.knowledge_gaps.length
        ? h("ul", { class: "gap-list" }, c.knowledge_gaps.map((g) => gapItem(g)))
        : h("p", { class: "muted" }, "None identified.")),

    h("section", {}, h("h3", {}, "Confidence"),
      h("p", {}, chip(c.confidence.level), " ", c.confidence.reason)));
}

async function viewConversations(routeId) {
  const list_ = await api("/conversations");
  setCount(list_.length, state.total);
  if (!list_.length) return emptyPanel();
  let selected = routeId ? list_.find((c) => c.id === routeId) : list_[0];
  let hidden = false;
  if (!selected && routeId) {
    selected = await api(`/conversations/${encodeURIComponent(routeId)}`, { filtered: false });
    hidden = true;
  }
  if (!selected) selected = list_[0];
  const nav = h("ul", { class: "conv-list", "aria-label": "Conversations" }, list_.map((c) =>
    h("li", {}, h("a", { href: `#/conversations/${encodeURIComponent(c.id)}`, "aria-current": c.id === selected.id ? "true" : null },
      h("div", { class: "row" }, h("span", { class: "id" }, c.id), chip(c.resolution.status, resClass(c.resolution.status))),
      h("span", { class: "snip" }, firstSentence(c.summary)),
      h("div", { class: "chips" }, chip(c.intent.value), chip(c.language.value), chip(`${c.overall_risk} risk`, riskClass(c.overall_risk)))))));
  return h("div", { class: "conv" }, nav, conversationDetail(selected, hidden));
}

async function viewGaps() {
  const d = await api("/analytics/knowledge-gaps");
  if (state.total == null) state.total = (await api("/analytics/overview", { filtered: false })).total;
  setCount(d.shown, state.total);
  if (!d.shown) return emptyPanel();
  const groups = {};
  for (const g of d.gaps) (groups[g.kind] ||= []).push(g);
  const kinds = Object.keys(KIND_LABELS).filter((k) => groups[k]).concat(Object.keys(groups).filter((k) => !KIND_LABELS[k]));
  const byCall = {};
  for (const f of d.flags) (byCall[f.call_id] ||= []).push(f.flag);

  return h("div", {},
    h("h2", {}, "Knowledge gaps"),
    h("p", { class: "muted" }, "Statements that could not be confirmed from the transcript, and programme information that was not supplied. An unsupported statement is not necessarily false; it is attributed to the speaker and needs an authoritative source."),
    h("div", { class: "kg-groups" }, kinds.map((k) =>
      h("section", {}, h("h3", {}, KIND_LABELS[k] || k, h("span", { class: "muted num small" }, `${groups[k].length}`)),
        h("ul", { class: "gap-list" }, groups[k].map((g) => gapItem(g, true)))))),
    h("div", { class: "two-col" },
      h("section", {}, h("h3", {}, "Programme information not supplied"),
        d.programme_info_not_supplied.length
          ? h("ul", { class: "gap-list" }, d.programme_info_not_supplied.map((p) =>
              h("li", {}, p.statement, h("div", { class: "meta" }, "Seen in: ", p.call_ids.map((id, i) => [i ? ", " : "", idLink(id)])))))
          : h("p", { class: "muted" }, "None recorded.")),
      h("section", {}, h("h3", {}, "Flags"),
        h("p", { class: "muted small" }, "Instructions inside a transcript are conversation content. They never change how a call is classified."),
        Object.keys(byCall).length
          ? h("ul", { class: "flag-list" }, Object.entries(byCall).map(([id, fl]) => h("li", {}, idLink(id), ": ", fl.join("; "))))
          : h("p", { class: "muted" }, "No flags."))));
}

/* ---------- routing and filters ---------- */
function parseRoute() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return { name: parts[0] || "overview", id: parts[1] ? decodeURIComponent(parts[1]) : null };
}

async function render() {
  const token = ++renderToken;
  const route = parseRoute();
  document.querySelectorAll(".tabs a").forEach((a) => {
    if (a.dataset.route === route.name) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  const main = $("#main");
  const views = {
    overview: viewOverview, resolution: viewResolution, risks: viewRisks,
    conversations: () => viewConversations(route.id), gaps: viewGaps,
  };
  const view = views[route.name] || viewOverview;
  main.replaceChildren(h("p", { class: "status", role: "status" }, "Loading…"));
  try {
    const node = await view();
    if (token !== renderToken) return;
    main.replaceChildren(node);
  } catch (err) {
    if (token !== renderToken) return;
    $("#count").textContent = "Showing no data";
    main.replaceChildren(errorPanel(err));
  }
}

function resetFilters() {
  for (const k of Object.keys(state.filters)) state.filters[k] = "";
  document.querySelectorAll("#filter-fields select").forEach((s) => { s.value = ""; });
  render();
}

async function buildFilters() {
  const box = $("#filter-fields");
  let opts = {};
  try { opts = await api("/filters", { filtered: false }); } catch { /* error panel will show from render() */ }
  box.replaceChildren(...FILTER_DEFS.map((f) => {
    const sel = h("select", { id: `f-${f.key}`, onchange: (e) => { state.filters[f.key] = e.target.value; render(); } },
      h("option", { value: "" }, "All"),
      (opts[f.key] || []).map((o) => h("option", { value: o }, o)));
    return h("label", { for: `f-${f.key}`, title: f.title || null }, f.label, sel);
  }));
}

$("#reset").addEventListener("click", resetFilters);
window.addEventListener("hashchange", () => {
  const before = document.querySelector(".tabs a[aria-current]")?.dataset.route;
  render().then(() => { if (parseRoute().name !== before) window.scrollTo(0, 0); });
});
buildFilters().then(render);
