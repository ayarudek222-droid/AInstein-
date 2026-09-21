// Ask, on the public site: a small Vercel function that holds the Anthropic
// API key and forwards the conversation. The key never reaches the browser.
//
// Set in Vercel → Project → Settings → Environment Variables:
//   ANTHROPIC_API_KEY   required (from console.anthropic.com)
//   ASK_PER_HOUR        optional, questions per visitor per hour (default 20)
//
// Every question is paid by the key's owner, so there is a per-visitor limit.
// It is kept in memory, so it is approximate (each server instance counts on
// its own); for a hard cap, set a monthly spend limit in the Anthropic console.

const MODELS = { quick: "claude-haiku-4-5-20251001", default: "claude-sonnet-5" };
const hits = new Map();

function limited(ip, perHour) {
  const now = Date.now(), list = (hits.get(ip) || []).filter(t => now - t < 3600e3);
  if (list.length >= perHour) { hits.set(ip, list); return true; }
  list.push(now); hits.set(ip, list); return false;
}

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: { code: "method" } });
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return res.status(501).json({ error: { code: "sampling_disabled", message: "ANTHROPIC_API_KEY is not set on the server." } });

  const ip = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim() || "unknown";
  if (limited(ip, Number(process.env.ASK_PER_HOUR || 20))) return res.status(429).json({ error: { code: "rate_limited" } });

  const body = req.body || {};
  const messages = Array.isArray(body.messages) ? body.messages.slice(-30) : [];
  if (!messages.length || JSON.stringify(messages).length > 60000)
    return res.status(400).json({ error: { code: "prompt_too_large" } });
  const tools = (Array.isArray(body.tools) ? body.tools : []).slice(0, 4).map(t => ({
    name: String(t.name).slice(0, 64), description: String(t.description || "").slice(0, 500),
    input_schema: t.input_schema || { type: "object", properties: {} },
  }));

  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({
        model: MODELS[body.tier] || MODELS.quick,
        max_tokens: body.tier === "default" ? 1500 : 900,
        messages,
        ...(tools.length ? { tools } : {}),
      }),
    });
    const data = await r.json();
    if (!r.ok) return res.status(r.status === 429 ? 429 : 502).json({ error: { code: r.status === 429 ? "rate_limited" : "upstream_error", message: data?.error?.message } });
    return res.status(200).json({ content: data.content, stop_reason: data.stop_reason });
  } catch (e) {
    return res.status(502).json({ error: { code: "upstream_error", message: String(e && e.message) } });
  }
};
