const TOOLS_URL = process.env.TOOLS_URL || "http://localhost:8000";

export async function callTool(name: string, args: object) {
  const res = await fetch(`${TOOLS_URL}/tool`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ name, args })
  });
  return res.json();
}
