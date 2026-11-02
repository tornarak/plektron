# Deploying the site

`harness site build` writes the site, and this directory puts it on Cloudflare as
a Worker with static assets and no script: `plectrum-press`, at `plectrum.press`.

Once, for the tools (`cf build` needs both `cf` and Wrangler installed locally):

    npm install

Each time, from this directory:

    uv run harness site build /run/user/1000/site
    export SITE_OUT=/run/user/1000/site    # default ../../dist
    cf build
    cf deploy --prebuilt

`cf build` copies the site to `.cloudflare/output/`. An upload sends only files
whose content is new.

Run `cf` from here, never from inside the site's directory: it leaves its
`.cloudflare/` cache in whatever directory it runs from, and the next upload from
there would publish that cache, which holds the account's details.

**Addresses.** A page is `x/index.html` and is served at `x`. `x/` and
`x/index.html` redirect there, and a colon in a path redirects once to `%3A`.
Anything else gets the site's `404.html`.

**Left out of the upload:** whatever `.assetsignore` names, which `site build`
writes (`harness/web/site.py`).

**Limits on the free plan:** 20,000 files per version, 25 MiB per file.

**Don't turn on** `cache` in `cloudflare.config.ts`: Workers Caching bills per
request, and static requests are otherwise free.
