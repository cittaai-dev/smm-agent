# smm-agent

A grounded, citation-verified AI agent that automates SOP-01 "Market Research" for a social media agency
workflow. See [CLAUDE.md](CLAUDE.md) for architecture, engineering principles, and the staged build plan;
see [TESTING.md](TESTING.md) for the testing policy.

Status: Steps 1-6 (`docs/implement/`) are implemented and merged to `main`. Check `git log` for current
progress rather than trusting a status line in a doc — it goes stale fast.

## Layout

- `backend/` — FastAPI + LangGraph orchestration + Postgres/pgvector + Celery/Redis
- `frontend/` — Next.js (App Router)
- `infra/` — docker-compose for local dev (postgres+pgvector, redis)
- `docs/` — SOPs, templates, architecture diagram, and the `implement/` build plan

## Local development

Both `backend/Dockerfile` and `frontend/Dockerfile` `COPY` source into the image at build time — there's no
bind mount. **`docker compose up -d` alone reuses whatever image was last built and will silently keep
serving old code after you edit a file.** Use the `Makefile` instead of raw `docker compose` commands so a
rebuild is never something you have to remember:

```
make up                # build (stamped with the current git sha) + start everything
make restart            # down, then up (with rebuild)
make rebuild-frontend    # rebuild + restart just the frontend
make rebuild-backend    # rebuild + restart backend + all Celery workers + beat
make logs
```

`/health/live` and the frontend's `/system-status` page both show the git sha baked into their running
container — compare it against `git rev-parse --short HEAD` if a change doesn't seem to be taking effect.
