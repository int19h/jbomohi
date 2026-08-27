"use strict";

const state = {
  data: null,
  query: "",
  view: "all",
  actor: null,
  selected: null,
  refreshing: false,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const els = {
  workspace: $(".workspace"),
  healthCard: $("#health-card"),
  healthLabel: $("#health-label"),
  healthDetail: $("#health-detail"),
  refresh: $("#refresh-button"),
  search: $("#search-input"),
  people: $("#people-list"),
  clearActor: $("#clear-actor"),
  list: $("#thread-list"),
  resultCount: $("#result-count"),
  activeView: $("#active-view-label"),
  filterSummary: $("#filter-summary"),
  reader: $("#thread-reader"),
  readerEmpty: $("#reader-empty"),
  readerContent: $("#reader-content"),
  protocol: $("#protocol-label"),
  mobileBack: $("#mobile-back"),
  toast: $("#toast"),
};

const palette = ["#f0a45d", "#66c8cc", "#b6a0e8", "#72c69d", "#e98793", "#7cadd8", "#d2bd72"];
const viewNames = {
  all: "All conversations",
  pending: "Awaiting disposition",
  decisions: "Decision questions",
  proposals: "Proposals",
  broadcasts: "Broadcast traffic",
};

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

function actorModel(actor = "") {
  return actor.match(/^([a-z][a-z0-9]*)_\d/)?.[1] || actor;
}

function actorColor(actor) {
  const name = actorModel(actor);
  let hash = 0;
  for (const char of name) hash = ((hash << 5) - hash + char.charCodeAt(0)) | 0;
  return palette[Math.abs(hash) % palette.length];
}

function actorInitials(actor) {
  const model = actorModel(actor);
  const known = { codex: "CX", fable: "FB", human: "HU" };
  return known[model] || model.slice(0, 2).toUpperCase();
}

function actorLabel(actor) {
  const session = state.data?.sessions.find(item => item.id === actor);
  if (session) return session.display_name || session.model;
  const model = state.data?.models.find(item => item.id === actorModel(actor));
  return model?.display_name || actor;
}

function avatar(actor, small = false) {
  const title = `${actorLabel(actor)} · ${actor}`;
  return `<span class="avatar${small ? " is-small" : ""}" style="--avatar:${actorColor(actor)}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${escapeHtml(actorInitials(actor))}</span>`;
}

function relativeTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value || "Unknown time";
  const seconds = Math.round((date.valueOf() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  const ranges = [[60, "second"], [60, "minute"], [24, "hour"], [7, "day"], [4.35, "week"], [12, "month"], [Infinity, "year"]];
  let amount = seconds;
  for (const [limit, unit] of ranges) {
    if (Math.abs(amount) < limit) return formatter.format(Math.round(amount), unit);
    amount /= limit;
  }
  return date.toLocaleDateString();
}

function fullTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value || "Unknown time";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function inlineMarkdown(raw) {
  const code = [];
  const links = [];
  let text = String(raw).replace(/`([^`]+)`/g, (_, value) => {
    code.push(`<code>${escapeHtml(value)}</code>`);
    return `\u0000CODE${code.length - 1}\u0000`;
  });
  text = text.replace(/\[([^\]]+)]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => {
    try {
      const parsed = new URL(url);
      if (!["http:", "https:"].includes(parsed.protocol)) return label;
      links.push(`<a href="${escapeHtml(parsed.href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`);
      return `\u0000LINK${links.length - 1}\u0000`;
    } catch {
      return label;
    }
  });
  text = escapeHtml(text);
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  text = text.replace(/~~([^~]+)~~/g, "<del>$1</del>");
  text = text.replace(/(^|\s)\*([^*\n]+)\*(?=\s|[.,;:!?]|$)/g, "$1<em>$2</em>");
  text = text.replace(/\u0000CODE(\d+)\u0000/g, (_, index) => code[Number(index)]);
  text = text.replace(/\u0000LINK(\d+)\u0000/g, (_, index) => links[Number(index)]);
  return text;
}

function renderMarkdown(markdown = "") {
  const lines = String(markdown).replace(/\r/g, "").split("\n");
  const output = [];
  let paragraph = [];
  let list = null;
  let fence = null;
  let fenceLines = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    output.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  };
  const closeList = () => {
    if (!list) return;
    output.push(`</${list}>`);
    list = null;
  };
  const openList = type => {
    if (list === type) return;
    closeList();
    output.push(`<${type}>`);
    list = type;
  };

  for (const line of lines) {
    const fenceMatch = line.match(/^\s*```\s*([^\s]*)/);
    if (fenceMatch) {
      flushParagraph(); closeList();
      if (fence === null) {
        fence = fenceMatch[1] || "";
        fenceLines = [];
      } else {
        output.push(`<pre><code${fence ? ` class="language-${escapeHtml(fence)}"` : ""}>${escapeHtml(fenceLines.join("\n"))}</code></pre>`);
        fence = null; fenceLines = [];
      }
      continue;
    }
    if (fence !== null) { fenceLines.push(line); continue; }
    if (!line.trim()) { flushParagraph(); closeList(); continue; }

    const heading = line.match(/^\s{0,3}(#{1,4})\s+(.+)$/);
    const bullet = line.match(/^\s*[-*+]\s+(.+)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    const quote = line.match(/^\s*>\s?(.*)$/);
    if (heading) {
      flushParagraph(); closeList();
      const level = heading[1].length;
      output.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
    } else if (/^\s*(---+|___+|\*\*\*+)\s*$/.test(line)) {
      flushParagraph(); closeList(); output.push("<hr>");
    } else if (bullet) {
      flushParagraph(); openList("ul"); output.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
    } else if (numbered) {
      flushParagraph(); openList("ol"); output.push(`<li>${inlineMarkdown(numbered[1])}</li>`);
    } else if (quote) {
      flushParagraph(); closeList(); output.push(`<blockquote>${inlineMarkdown(quote[1])}</blockquote>`);
    } else {
      closeList(); paragraph.push(line.trim());
    }
  }
  if (fence !== null) output.push(`<pre><code>${escapeHtml(fenceLines.join("\n"))}</code></pre>`);
  flushParagraph(); closeList();
  return output.join("\n");
}

function messageMap() {
  return new Map(state.data.messages.map(message => [message.id, message]));
}

function threadSearchText(thread) {
  const map = messageMap();
  return thread.message_ids.map(id => {
    const message = map.get(id);
    return [message.id, message.title, message.body, message.from, ...message.to, ...message.github_issues].join(" ");
  }).join(" ").toLowerCase();
}

function matchesActor(thread, actor) {
  if (!actor) return true;
  const model = actorModel(actor);
  return thread.participants.some(participant => participant === actor || actorModel(participant) === model);
}

function filteredThreads() {
  if (!state.data) return [];
  const query = state.query.trim().toLowerCase();
  return state.data.threads.filter(thread => {
    if (!matchesActor(thread, state.actor)) return false;
    if (state.view === "pending" && !thread.pending_for.length) return false;
    if (state.view === "decisions" && !thread.kinds.includes("decision-query")) return false;
    if (state.view === "proposals" && !thread.kinds.includes("proposal")) return false;
    if (state.view === "broadcasts" && !thread.has_broadcast) return false;
    return !query || threadSearchText(thread).includes(query);
  });
}

function kindLabel(kind) {
  return (kind || "message").replaceAll("-", " ");
}

function renderHealth() {
  const { data } = state;
  els.healthCard.classList.toggle("is-healthy", data.healthy);
  els.healthCard.classList.toggle("is-unhealthy", !data.healthy);
  els.healthLabel.textContent = data.healthy ? "Exchange healthy" : (data.stale ? "Showing last good read" : "Validation warnings");
  els.healthDetail.textContent = data.healthy
    ? `${data.stats.messages} messages · ${data.stats.acknowledgements} acks`
    : `${data.errors.length} issue${data.errors.length === 1 ? "" : "s"} · click for details`;
  els.healthCard.title = data.errors.join("\n");
  els.protocol.textContent = data.protocol.replace("jbomohi-mail/", "Protocol ");
}

function renderCounts() {
  const threads = state.data.threads;
  $("#count-all").textContent = threads.length;
  $("#count-pending").textContent = threads.filter(thread => thread.pending_for.length).length;
  $("#count-decisions").textContent = threads.filter(thread => thread.kinds.includes("decision-query")).length;
  $("#count-proposals").textContent = threads.filter(thread => thread.kinds.includes("proposal")).length;
  $("#count-broadcasts").textContent = threads.filter(thread => thread.has_broadcast).length;
}

function renderPeople() {
  const sessions = [...state.data.sessions].sort((a, b) => {
    if (a.status !== b.status) return a.status === "active" ? -1 : 1;
    return a.id.localeCompare(b.id);
  });
  els.people.innerHTML = sessions.map(session => `
    <button class="person-button${state.actor === session.id ? " is-active" : ""}" type="button" data-actor="${escapeHtml(session.id)}" aria-pressed="${state.actor === session.id}">
      ${avatar(session.id)}
      <span class="person-meta"><strong>${escapeHtml(session.display_name)}</strong><span>${escapeHtml(session.id)}</span></span>
      <span class="session-state${session.status === "active" ? " is-active" : ""}" title="${escapeHtml(session.status)}"></span>
    </button>`).join("") || '<p class="empty-list">No sessions registered.</p>';
  els.clearActor.hidden = !state.actor;
}

function avatarStack(participants) {
  const shown = participants.slice(0, 4);
  return `<span class="avatar-stack" aria-label="${escapeHtml(participants.join(", "))}">${shown.map(actor => avatar(actor, true)).join("")}${participants.length > shown.length ? `<span class="avatar-more">+${participants.length - shown.length}</span>` : ""}</span>`;
}

function renderThreadList() {
  const threads = filteredThreads();
  els.list.setAttribute("aria-busy", "false");
  els.resultCount.textContent = `${threads.length} thread${threads.length === 1 ? "" : "s"}`;
  els.activeView.textContent = viewNames[state.view];
  const summaries = [];
  if (state.actor) summaries.push(`session: ${state.actor}`);
  if (state.query.trim()) summaries.push(`search: “${state.query.trim()}”`);
  els.filterSummary.hidden = !summaries.length;
  els.filterSummary.textContent = summaries.join(" · ");
  if (!threads.length) {
    els.list.innerHTML = '<div class="empty-list"><strong>No matching thread</strong>Try a broader search or clear the active filter.</div>';
    return;
  }
  els.list.innerHTML = threads.map(thread => {
    const flags = [
      thread.pending_for.length ? `<span class="mini-flag is-pending">${thread.pending_for.length} pending</span>` : "",
      thread.has_broadcast ? '<span class="mini-flag is-broadcast">all</span>' : "",
    ].join("");
    return `<button class="thread-row${state.selected === thread.id ? " is-active" : ""}" type="button" data-thread="${escapeHtml(thread.id)}" aria-pressed="${state.selected === thread.id}">
      <span class="thread-row-head"><span class="thread-kind">${escapeHtml(kindLabel(thread.kinds[0]))}</span><time class="thread-time" datetime="${escapeHtml(thread.last_activity_utc)}" title="${escapeHtml(fullTime(thread.last_activity_utc))}">${escapeHtml(relativeTime(thread.last_activity_utc))}</time></span>
      <h3>${escapeHtml(thread.title)}</h3>
      <p>${escapeHtml(thread.excerpt || "No summary available.")}</p>
      <span class="thread-row-foot">${avatarStack(thread.participants)}<span class="thread-flags">${flags}<span class="thread-count">${thread.message_ids.length} msg</span></span></span>
    </button>`;
  }).join("");
}

function orderedMessages(thread) {
  const map = messageMap();
  const members = new Set(thread.message_ids);
  const ordered = [];
  const visited = new Set();
  const visit = id => {
    if (visited.has(id) || !members.has(id) || !map.has(id)) return;
    visited.add(id);
    const message = map.get(id);
    ordered.push(message);
    [...message.replies].sort().forEach(visit);
  };
  visit(thread.id);
  thread.message_ids.forEach(visit);
  return ordered;
}

function messageStatus(message) {
  if (!message.ack_required) return { label: "FYI", className: "complete" };
  if (message.pending_for.length) return { label: `${message.pending_for.length} pending`, className: "pending" };
  if (message.addressed_without_ack.length && !message.acked_by.length) return { label: "Addressed", className: "complete" };
  return { label: "Disposition captured", className: "complete" };
}

function relationNote(message) {
  const notes = [];
  if (message.in_reply_to !== "none") notes.push(`Reply to <button class="jump-link" type="button" data-jump="${escapeHtml(message.in_reply_to)}">${escapeHtml(message.in_reply_to)}</button>`);
  if (message.supersedes !== "none") notes.push(`Supersedes <button class="jump-link" type="button" data-jump="${escapeHtml(message.supersedes)}">${escapeHtml(message.supersedes)}</button>`);
  if (message.superseded_by.length) notes.push(`Superseded by ${message.superseded_by.map(id => `<button class="jump-link" type="button" data-jump="${escapeHtml(id)}">${escapeHtml(id)}</button>`).join(" ")}`);
  return notes.length ? `<div class="relation-note">${notes.join(" · ")}</div>` : "";
}

function renderRoutes(message) {
  const rawRecipients = message.to.map(actor => `<span class="route-chip">to ${escapeHtml(actor)}</span>`).join("");
  const pending = message.pending_for.map(actor => `<span class="route-chip is-pending">pending ${escapeHtml(actor)}</span>`).join("");
  const addressed = message.addressed_without_ack.map(actor => `<span class="route-chip is-addressed">addressed ${escapeHtml(actor)}</span>`).join("");
  const acked = message.acked_by.map(actor => `<span class="route-chip is-acked">✓ ${escapeHtml(actor)}</span>`).join("");
  const details = message.acknowledgements.length ? `
    <details class="ack-details">
      <summary>${message.acknowledgements.length} acknowledgement disposition${message.acknowledgements.length === 1 ? "" : "s"}</summary>
      ${message.acknowledgements.map(ack => `<div class="ack-entry"><strong>${escapeHtml(ack.by)}</strong><span>${escapeHtml(ack.disposition || "Disposition captured")}</span><time datetime="${escapeHtml(ack.created_utc)}">${escapeHtml(fullTime(ack.created_utc))}</time></div>`).join("")}
    </details>` : "";
  return rawRecipients + pending + addressed + acked + details;
}

function renderMessage(message) {
  const status = messageStatus(message);
  const sender = actorLabel(message.from);
  const pills = [
    `<span class="pill kind">${escapeHtml(kindLabel(message.kind))}</span>`,
    `<span class="pill ${status.className}">${escapeHtml(status.label)}</span>`,
    message.audience === "all" ? '<span class="pill broadcast">Broadcast</span>' : "",
    message.superseded_by.length ? '<span class="pill superseded">Superseded</span>' : "",
  ].join("");
  const issues = message.github_issues.map(issue => `<a class="issue-link" href="https://github.com/int19h/jbomohi/issues/${issue.slice(1)}" target="_blank" rel="noopener noreferrer">${escapeHtml(issue)}</a>`).join("");
  return `${relationNote(message)}
    <section class="message-node${message.depth ? " is-reply" : ""}" id="message-${escapeHtml(message.id)}" style="--depth:${Math.min(message.depth, 3)}">
      ${avatar(message.from)}
      <article class="message-card${message.superseded_by.length ? " is-superseded" : ""}">
        <header class="message-header">
          <div><div class="author-line"><strong>${escapeHtml(sender)}</strong><span>${escapeHtml(message.from)}</span></div><div class="message-routing">${escapeHtml(message.model || "model unspecified")} · ${escapeHtml(message.client || "client unspecified")}</div></div>
          <div class="message-actions"><time class="message-time" datetime="${escapeHtml(message.created_utc)}" title="${escapeHtml(fullTime(message.created_utc))}">${escapeHtml(relativeTime(message.created_utc))}</time><button class="copy-button" type="button" data-copy="${escapeHtml(message.id)}" title="Copy message id">ID</button></div>
        </header>
        <div class="message-body">${renderMarkdown(message.body)}</div>
        <footer class="message-footer">${pills}${issues}${renderRoutes(message)}</footer>
      </article>
    </section>`;
}

function renderReader({ focus = false } = {}) {
  if (!state.data || !state.selected) {
    els.readerEmpty.hidden = false;
    els.readerContent.hidden = true;
    return;
  }
  const thread = state.data.threads.find(item => item.id === state.selected);
  if (!thread) {
    state.selected = null;
    renderReader();
    return;
  }
  const messages = orderedMessages(thread);
  const issueLinks = thread.github_issues.map(issue => `<a class="issue-link" href="https://github.com/int19h/jbomohi/issues/${issue.slice(1)}" target="_blank" rel="noopener noreferrer">${escapeHtml(issue)}</a>`).join("");
  const flags = [
    thread.pending_for.length ? `<span class="pill pending">${thread.pending_for.length} awaiting disposition</span>` : '<span class="pill complete">Thread clear</span>',
    thread.has_broadcast ? '<span class="pill broadcast">Includes broadcast</span>' : "",
    thread.superseded ? '<span class="pill superseded">Root superseded</span>' : "",
  ].join("");
  els.readerContent.innerHTML = `
    <header class="conversation-header">
      <div class="conversation-overline"><span class="pill kind">${escapeHtml(kindLabel(thread.kinds[0]))}</span>${flags}</div>
      <h2>${escapeHtml(thread.title)}</h2>
      <p>${escapeHtml(thread.excerpt || "An exchange conversation.")}</p>
      <div class="conversation-summary">
        ${avatarStack(thread.participants)}
        <span class="summary-item">${thread.participants.length} participant${thread.participants.length === 1 ? "" : "s"}</span>
        <span class="summary-item">${messages.length} message${messages.length === 1 ? "" : "s"}</span>
        <span class="summary-item">updated ${escapeHtml(relativeTime(thread.last_activity_utc))}</span>
        ${issueLinks}
      </div>
    </header>
    <div class="message-timeline">${messages.map(renderMessage).join("")}</div>`;
  els.readerEmpty.hidden = true;
  els.readerContent.hidden = false;
  els.workspace.classList.add("is-reading");
  if (focus) els.reader.focus({ preventScroll: true });
}

function renderAll() {
  renderHealth();
  renderCounts();
  renderPeople();
  renderThreadList();
  renderReader();
}

function selectThread(id, { updateHash = true, focus = false } = {}) {
  if (!state.data?.threads.some(thread => thread.id === id)) return;
  state.selected = id;
  if (updateHash) history.replaceState(null, "", `#${encodeURIComponent(id)}`);
  renderThreadList();
  renderReader({ focus });
  els.reader.scrollTop = 0;
}

function hashSelection() {
  const raw = decodeURIComponent(location.hash.slice(1));
  if (!raw || !state.data) return null;
  const thread = state.data.threads.find(item => item.id === raw);
  if (thread) return thread.id;
  return state.data.messages.find(message => message.id === raw)?.root_id || null;
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("is-visible");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => els.toast.classList.remove("is-visible"), 1800);
}

async function loadData({ silent = false } = {}) {
  if (state.refreshing) return;
  state.refreshing = true;
  els.refresh.classList.add("is-spinning");
  try {
    const response = await fetch("/api/snapshot", { cache: "no-store" });
    if (!response.ok) throw new Error(`Reader returned ${response.status}`);
    const incoming = await response.json();
    const previousCount = state.data?.stats.messages;
    state.data = incoming;
    const requested = hashSelection();
    if (requested) state.selected = requested;
    if (!state.selected || !incoming.threads.some(thread => thread.id === state.selected)) {
      state.selected = incoming.threads[0]?.id || null;
    }
    renderAll();
    if (!silent && previousCount !== undefined) {
      const delta = incoming.stats.messages - previousCount;
      showToast(delta ? `${Math.abs(delta)} message${Math.abs(delta) === 1 ? "" : "s"} ${delta > 0 ? "added" : "removed"}` : "Exchange is up to date");
    }
  } catch (error) {
    els.healthCard.classList.remove("is-healthy");
    els.healthCard.classList.add("is-unhealthy");
    els.healthLabel.textContent = "Reader disconnected";
    els.healthDetail.textContent = error.message;
    if (!silent) showToast("Could not refresh the exchange");
  } finally {
    state.refreshing = false;
    els.refresh.classList.remove("is-spinning");
  }
}

$$('[data-view]').forEach(button => button.addEventListener("click", () => {
  state.view = button.dataset.view;
  $$('[data-view]').forEach(item => item.classList.toggle("is-active", item === button));
  renderThreadList();
}));

els.search.addEventListener("input", () => {
  state.query = els.search.value;
  renderThreadList();
});

els.list.addEventListener("click", event => {
  const button = event.target.closest("[data-thread]");
  if (button) selectThread(button.dataset.thread, { focus: true });
});

els.people.addEventListener("click", event => {
  const button = event.target.closest("[data-actor]");
  if (!button) return;
  state.actor = state.actor === button.dataset.actor ? null : button.dataset.actor;
  renderPeople(); renderThreadList();
});

els.clearActor.addEventListener("click", () => {
  state.actor = null; renderPeople(); renderThreadList();
});

els.readerContent.addEventListener("click", async event => {
  const copy = event.target.closest("[data-copy]");
  const jump = event.target.closest("[data-jump]");
  if (copy) {
    try { await navigator.clipboard.writeText(copy.dataset.copy); showToast("Message ID copied"); }
    catch { showToast("Copy unavailable"); }
  }
  if (jump) {
    const target = $(`#message-${CSS.escape(jump.dataset.jump)}`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
});

els.refresh.addEventListener("click", () => loadData());
els.mobileBack.addEventListener("click", () => {
  els.workspace.classList.remove("is-reading");
  $("#thread-index").focus?.();
});

window.addEventListener("hashchange", () => {
  const requested = hashSelection();
  if (requested && requested !== state.selected) selectThread(requested, { updateHash: false });
});

document.addEventListener("keydown", event => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (event.key === "/" && !typing) {
    event.preventDefault(); els.search.focus();
  }
  if (event.key === "Escape" && typing) {
    els.search.value = ""; state.query = ""; els.search.blur(); renderThreadList();
  }
  if (!typing && ["j", "k"].includes(event.key.toLowerCase())) {
    const threads = filteredThreads();
    if (!threads.length) return;
    event.preventDefault();
    const current = Math.max(0, threads.findIndex(thread => thread.id === state.selected));
    const offset = event.key.toLowerCase() === "j" ? 1 : -1;
    const next = threads[Math.min(threads.length - 1, Math.max(0, current + offset))];
    selectThread(next.id);
    $(`[data-thread="${CSS.escape(next.id)}"]`)?.scrollIntoView({ block: "nearest" });
  }
});

loadData({ silent: true });
setInterval(() => loadData({ silent: true }), 8000);
