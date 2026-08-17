# Vercel Docker Deployment

This project deploys as one Vercel container using `Dockerfile.vercel`.

The container runs:

- Next.js on `127.0.0.1:3000`
- FastAPI on `127.0.0.1:8000`
- nginx on `$PORT`, routing `/` to Next.js and `/api/*` to FastAPI

## Required Vercel Settings

Import the GitHub repo in Vercel and keep the project root as the repository root.

Add production environment variables in Vercel Project Settings. Do not rely on `.env` being copied into the image.

Minimum variables:

```env
DATABASE_URL=
JWT_SECRET_KEY=
ENCRYPTION_KEY=
APP_BASE_URL=https://your-vercel-domain.vercel.app/api
FRONTEND_APP_URL=https://your-vercel-domain.vercel.app
CORS_ALLOWED_ORIGINS=https://your-vercel-domain.vercel.app
RATE_LIMITING_ENABLED=true
RATE_LIMIT_REDIS_URL=
CACHE_REDIS_URL=
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=
OPENAI_API_KEY=
```

Also set the Google, Gemini, Anthropic, and Calendly variables if those features are enabled.

## Frontend API URL

The Docker build sets:

```env
NEXT_PUBLIC_API_BASE_URL=/api
```

That makes browser requests same-origin, for example `/api/auth/login`. nginx strips `/api` before forwarding to FastAPI, so the backend still receives `/auth/login`.

## GitHub Checklist

The root repo must contain the actual `frontend` files. If Git shows `frontend` as an embedded repo or gitlink, Vercel may not receive the frontend source.

Check with:

```powershell
git ls-files --stage frontend
```

If the output starts with `160000`, convert `frontend` from an embedded repo into normal tracked files before pushing.
