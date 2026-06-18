/**
 * Worker Cloudflare — gestion des "sessions de veille".
 *
 * Reçoit { action: "add" | "delete" | "list", secret, words?, name?, id? },
 * vérifie la phrase secrète, met à jour sessions.json dans le repo via l'API
 * GitHub, puis relance la veille (workflow monitor.yml). Le token GitHub reste
 * côté serveur — jamais exposé dans la page.
 *
 * Variables à définir dans Cloudflare (Settings → Variables and Secrets) :
 *   GH_TOKEN        (Secret)   token GitHub fine-grained, repo veille-apl, droits
 *                              Contents: Read/Write + Actions: Read/Write
 *   SESSION_SECRET  (Secret)   votre phrase secrète (celle saisie dans le dashboard)
 *   GH_REPO         (Variable) "MHT-RIAD/veille-apl"
 *   ALLOW_ORIGIN    (Variable) "https://mht-riad.github.io"  (ou "*")
 */

function cors(env) {
  return {
    "Access-Control-Allow-Origin": env.ALLOW_ORIGIN || "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}
function json(obj, status, env) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "Content-Type": "application/json", ...cors(env) },
  });
}
function slug(s) {
  return (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "session";
}
function b64decode(b64) {
  const bin = atob((b64 || "").replace(/\n/g, ""));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}
function b64encode(str) {
  const bytes = new TextEncoder().encode(str);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}
function gh(env, path, init) {
  return fetch("https://api.github.com/repos/" + env.GH_REPO + path, {
    ...(init || {}),
    headers: {
      "Authorization": "Bearer " + env.GH_TOKEN,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "veille-apl-worker",
      "Content-Type": "application/json",
    },
  });
}

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(env) });
    if (req.method !== "POST") return json({ error: "POST uniquement" }, 405, env);

    let body;
    try { body = await req.json(); } catch { return json({ error: "JSON invalide" }, 400, env); }

    if (!env.SESSION_SECRET || body.secret !== env.SESSION_SECRET)
      return json({ error: "Phrase secrète incorrecte" }, 401, env);

    const action = body.action;
    const path = "/contents/sessions.json";

    // Lire l'état courant (sha + contenu)
    let sha = null, sessions = [];
    const r = await gh(env, path);
    if (r.status === 200) {
      const d = await r.json();
      sha = d.sha;
      try { sessions = (JSON.parse(b64decode(d.content)).sessions) || []; } catch { sessions = []; }
    } else if (r.status !== 404) {
      return json({ error: "Lecture GitHub échouée", status: r.status }, 502, env);
    }

    if (action === "list") return json({ sessions }, 200, env);

    if (action === "add") {
      const words = (body.words || []).map((w) => String(w).trim()).filter(Boolean).slice(0, 3);
      if (words.length < 2) return json({ error: "2 à 3 mots requis" }, 400, env);
      if (sessions.length >= 25) return json({ error: "Limite de 25 sessions atteinte" }, 400, env);
      const id = slug(words.join("-")) + "-" + Date.now().toString(36).slice(-4);
      sessions.push({ id, name: body.name || words.join(" · "), words, created: new Date().toISOString() });
    } else if (action === "delete") {
      const id = body.id;
      const before = sessions.length;
      sessions = sessions.filter((s) => s.id !== id);
      if (sessions.length === before) return json({ error: "Session introuvable" }, 404, env);
    } else {
      return json({ error: "Action inconnue" }, 400, env);
    }

    // Écrire sessions.json
    const content = b64encode(JSON.stringify({ sessions }, null, 2) + "\n");
    const put = await gh(env, path, {
      method: "PUT",
      body: JSON.stringify({ message: "sessions: " + action, content, sha: sha || undefined }),
    });
    if (!put.ok) {
      const detail = await put.text();
      return json({ error: "Écriture GitHub échouée", status: put.status, detail }, 502, env);
    }

    // Relancer la veille tout de suite (best-effort)
    try {
      await gh(env, "/actions/workflows/monitor.yml/dispatches", {
        method: "POST", body: JSON.stringify({ ref: "main" }),
      });
    } catch (e) { /* la veille horaire prendra le relais */ }

    return json({ ok: true, sessions }, 200, env);
  },
};
