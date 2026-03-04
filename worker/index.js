/**
 * Cloudflare Worker — Close GitHub Issue on "읽음" button click.
 *
 * Routes:
 *   POST /close/:issueNumber  — Close the issue and redirect to blog
 *   GET  /health              — Health check
 *
 * Environment variables (Cloudflare Worker Secrets):
 *   GITHUB_TOKEN   — GitHub PAT with issues:write scope
 *   GITHUB_REPO    — "owner/repo" format (e.g. "user/InsightFlow")
 *   BLOG_URL       — Blog base URL for redirect (e.g. "https://user.github.io/InsightFlow")
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return new Response("ok", { status: 200 });
    }

    const match = url.pathname.match(/^\/close\/(\d+)$/);
    if (!match) {
      return new Response("Not Found", { status: 404 });
    }

    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const issueNumber = match[1];
    const repo = env.GITHUB_REPO;
    const token = env.GITHUB_TOKEN;

    if (!repo || !token) {
      return new Response("Server misconfigured", { status: 500 });
    }

    const res = await fetch(
      `https://api.github.com/repos/${repo}/issues/${issueNumber}`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "InsightFlow-Worker/1.0",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ state: "closed" }),
      },
    );

    if (res.ok) {
      const blogUrl = env.BLOG_URL || "";
      return Response.redirect(`${blogUrl}/index.html`, 302);
    }

    const body = await res.text();
    console.error(`GitHub API error: ${res.status} ${body}`);
    return new Response("Failed to close issue. Please try again later.", {
      status: 502,
    });
  },
};
