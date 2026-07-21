# Route 1 — working notes for Claude

Read this before changing anything that ships. The full as-built runbook is
[`Route1/DEPLOY.md`](Route1/DEPLOY.md) — open it rather than guessing about infrastructure.

## Deploys: two separate paths, do not mix them

| Changed | How it goes live |
|---|---|
| Anything in `Route1/frontend` | `git push origin main`. GitHub Actions publishes to Pages automatically. **No SSH, no EC2, no systemctl.** |
| Anything in `Route1/backend` | SSH in → `cd ~/pathways && git pull && sudo systemctl restart route1` |

Restarting the `route1` service does nothing for a frontend change — it only restarts the API.
The frontend and backend are not on the same machine (Pages vs. EC2).

After a frontend push, **verify against the live site** instead of assuming:

```
curl -s https://route1pathways.app/styles.css | grep '<a rule you just added>'
```

## Frontend gotchas

- **Bump the cache-buster.** `index.html` loads `styles.css?v=YYYYMMDD<letter>`. If you change
  `styles.css` without bumping that string, browsers serve the old file and the change looks
  like it silently failed. Same idea applies to `app.js` if it ever gets one.
- **`app.js` is live code.** Class names in `styles.css` and the `id`s the JS looks up are
  load-bearing — renaming one to make markup tidier breaks behavior. For visual work, change
  styles, not structure, unless the task is explicitly a refactor.
- **Design intent lives in [`DESIGN.md`](DESIGN.md).** The short version: harvest gold is
  *semantic* — it marks rescued value, not decoration. Don't spend it on CRUD chrome.

## Local, gitignored notes

`*.local.md` (e.g. `OPERATIONS.local.md`, `AUDIT.local.md`) hold live credentials and are
excluded by `.gitignore`. **Never commit them, never paste their contents into code, commit
messages, or anything that leaves the machine.** They exist only on the maintainers' laptops;
if you need a value from one, ask.

## Working style

The maintainers are learning AWS/Linux/git. Give exact, copy-pasteable commands **one at a
time**, as single-line chains — some remote terminals mangle multi-line pastes. When something
is verified, say so plainly; when it isn't, say that too.
