# Install the Outpace production deployment files

From `/workspaces/outpace`, after uploading
`outpace-production-deployment.tar.gz`:

```bash
cd /workspaces/outpace || exit 1

tar -xzf outpace-production-deployment.tar.gz
rm outpace-production-deployment.tar.gz

python scripts/check_production_config.py
python -m compileall -q api workers
python -m pip check

cd frontend || exit 1
npm ci
npm run lint
npm run build
cd ..

git diff --check
git status --short
```

Review the production topology and environment-variable checklist:

```bash
sed -n '1,320p' docs/DEPLOYMENT.md
sed -n '1,320p' render.yaml
```

If the checks pass:

```bash
git add \
  .dockerignore \
  .env.example \
  .github/workflows/ci.yml \
  .gitignore \
  DEPLOYMENT_INSTALL.md \
  Dockerfile \
  docs/DEPLOYMENT.md \
  frontend/.env.example \
  render.yaml \
  requirements.txt \
  scripts/check_production_config.py

git commit -m "Add production deployment configuration"
git push origin main
```

Then create a new Blueprint in Render from the repository. Follow
`docs/DEPLOYMENT.md` for the secret values, public URLs, Supabase Auth redirect
settings, and production smoke test.
