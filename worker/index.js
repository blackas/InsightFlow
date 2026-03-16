/**
 * Cloudflare Worker health endpoint.
 *
 * Public issue-closing has been disabled until the project has a defensible
 * authentication model for privileged write actions.
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

    if (match) {
      return new Response("Issue closing is disabled on the public worker.", {
        status: 410,
      });
    }

    return new Response("Not Found", { status: 404 });
  },
};
