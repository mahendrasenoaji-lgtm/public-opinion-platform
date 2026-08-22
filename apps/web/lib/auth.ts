// Site-wide password gate — pre-launch lock.
// HMAC-SHA256 signed session cookie via Web Crypto (Edge-safe, no external deps).

export const COOKIE_NAME = "pop_gate_session";
export const COOKIE_MAX_AGE = 60 * 60 * 24 * 7; // 7 days

async function hmac(secret: string, data: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(data));
  return Buffer.from(sig).toString("base64url");
}

export async function createToken(secret: string): Promise<string> {
  const payload = String(Date.now());
  const sig = await hmac(secret, payload);
  return `${payload}.${sig}`;
}

export async function verifyToken(secret: string, token: string | undefined): Promise<boolean> {
  if (!token) return false;
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const expected = await hmac(secret, payload);
  if (expected.length !== sig.length) return false;
  // constant-time-ish compare
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i);
  if (diff !== 0) return false;
  const age = Date.now() - Number(payload);
  return age >= 0 && age <= COOKIE_MAX_AGE * 1000;
}
