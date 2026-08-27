const form = document.querySelector("#lookup-form");
const urlInput = document.querySelector("#linkedin-url");
const liAtInput = document.querySelector("#li-at");
const jsessionInput = document.querySelector("#jsessionid");
const button = document.querySelector("#submit-btn");
const message = document.querySelector("#message");
const result = document.querySelector("#result");

document.querySelectorAll(".info-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const panel = document.getElementById(btn.getAttribute("aria-controls"));
    const open = btn.getAttribute("aria-expanded") === "true";
    document.querySelectorAll(".help").forEach((el) => {
      el.hidden = true;
    });
    document.querySelectorAll(".info-btn").forEach((other) => {
      other.setAttribute("aria-expanded", "false");
    });
    if (!open && panel) {
      panel.hidden = false;
      btn.setAttribute("aria-expanded", "true");
    }
  });
});

function showMessage(text, isError) {
  message.hidden = !text;
  message.textContent = text;
  message.classList.toggle("error", Boolean(isError));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function multiline(value) {
  return escapeHtml(value).replaceAll("\n", "<br />");
}

function joinMeta(parts) {
  return parts.filter(Boolean).map(escapeHtml).join(" · ");
}

function field(label, value) {
  if (!value) return "";
  return `<div class="field">
    <dt>${escapeHtml(label)}</dt>
    <dd>${multiline(value)}</dd>
  </div>`;
}

function section(title, inner, show) {
  if (!show) return "";
  return `<section><h3>${escapeHtml(title)}</h3>${inner}</section>`;
}

function renderProfile(payload) {
  const profile = payload.profile || {};
  const photo = profile.image_url
    ? `<img class="avatar" src="${escapeHtml(profile.image_url)}" alt="${escapeHtml(profile.name || "Profile photo")}" />`
    : `<div class="avatar avatar-fallback" aria-hidden="true">${escapeHtml((profile.name || "?").slice(0, 1))}</div>`;

  const experience = (profile.experience || [])
    .map(
      (item) => `<li class="entry">
        <div class="entry-title">${escapeHtml(item.title)}</div>
        <div class="entry-org">${escapeHtml(item.company)}</div>
        <div class="entry-meta">${joinMeta([item.dates, item.location])}</div>
        ${item.description ? `<p class="entry-body">${multiline(item.description)}</p>` : ""}
      </li>`,
    )
    .join("");

  const education = (profile.education || [])
    .map(
      (item) => `<li class="entry">
        <div class="entry-title">${escapeHtml(item.school)}</div>
        <div class="entry-org">${joinMeta([item.degree, item.field])}</div>
        <div class="entry-meta">${escapeHtml(item.dates)}</div>
      </li>`,
    )
    .join("");

  const skills = (profile.skills || [])
    .map((skill) => `<li>${escapeHtml(skill)}</li>`)
    .join("");

  const certifications = (profile.certifications || [])
    .map(
      (item) => `<li class="entry">
        <div class="entry-title">${escapeHtml(item.name)}</div>
        <div class="entry-org">${escapeHtml(item.issuer)}</div>
        <div class="entry-meta">${escapeHtml(item.date)}</div>
      </li>`,
    )
    .join("");

  const languages = (profile.languages || [])
    .map(
      (item) => `<li class="entry">
        <div class="entry-title">${escapeHtml(item.name)}</div>
        <div class="entry-meta">${escapeHtml(item.proficiency)}</div>
      </li>`,
    )
    .join("");

  result.hidden = false;
  result.innerHTML = `
    <div class="profile-head">
      ${photo}
      <div>
        <p class="kicker">profile</p>
        <h2>${escapeHtml(profile.name) || "Name unavailable"}</h2>
        ${profile.headline ? `<p class="headline">${escapeHtml(profile.headline)}</p>` : ""}
        ${profile.location ? `<p class="muted">${escapeHtml(profile.location)}</p>` : ""}
      </div>
    </div>
    <dl class="fields">
      ${field("name", profile.name)}
      ${field("headline", profile.headline)}
      ${field("location", profile.location)}
      ${field("about", profile.about)}
      ${field("image_url", profile.image_url)}
    </dl>
    ${section("experience", `<ul class="timeline">${experience}</ul>`, experience.length > 0)}
    ${section("education", `<ul class="timeline">${education}</ul>`, education.length > 0)}
    ${section("skills", `<ul class="pills">${skills}</ul>`, skills.length > 0)}
    ${section("certifications", `<ul class="timeline">${certifications}</ul>`, certifications.length > 0)}
    ${section("languages", `<ul class="timeline">${languages}</ul>`, languages.length > 0)}
  `;
}

async function loadSession() {
  try {
    const response = await fetch("/ready");
    const data = await response.json();
    sessionStatus.hidden = false;
    if (data.session_configured) {
      sessionStatus.textContent = "Session cookies are loaded from .env.";
      sessionStatus.className = "status ok";
    } else {
      sessionStatus.textContent =
        "No LinkedIn cookies loaded. Save LINKEDIN_LI_AT and LINKEDIN_JSESSIONID in .env, then restart the server.";
      sessionStatus.className = "status bad";
    }
  } catch {
    sessionStatus.hidden = false;
    sessionStatus.textContent = "Could not reach the API.";
    sessionStatus.className = "status bad";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showMessage("");
  result.hidden = true;
  button.disabled = true;
  button.textContent = "Fetching…";
  try {
    const response = await fetch("/profile", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        linkedin_url: urlInput.value.trim(),
        li_at: liAtInput.value.trim(),
        jsessionid: jsessionInput.value.trim(),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data?.error?.message || `Request failed (${response.status})`;
      showMessage(detail, true);
      return;
    }
    renderProfile(data);
  } catch (error) {
    showMessage(error instanceof Error ? error.message : "Request failed", true);
  } finally {
    button.disabled = false;
    button.textContent = "Fetch profile";
  }
});
