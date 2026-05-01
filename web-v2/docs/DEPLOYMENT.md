## WOBD Deployment Instructions

These instructions are for deployment of the web app (code within the web-v2 directory) to an AWS EC2 instance.

### Steps to run on localhost
- On localhost, run `cd web-v2 && npm run build` (Note: stop the app on localhost if still running under `npm run dev`)

- Run a smoke-test of the built app at the **origin root** (no subpath):
`cd web-v2 && npm run build && npm start` → open `http://localhost:3000`

- To match **production** (subpath `/wobd`, same as the Docker image), build with the base path and open the app under that prefix:
`cd web-v2 && NEXT_PUBLIC_BASE_PATH=/wobd npm run build && NEXT_PUBLIC_BASE_PATH=/wobd npm start` → open `http://localhost:3000/wobd`

### Steps to run on the EC2 server

- SSH to the server, e.g. ssh -i <PATH-TO-YOUR-PRIVATE-SSH-KEY>  ubuntu@ec2-3-135-79-177.us-east-2.compute.amazonaws.com

- Navigate to the project directory:
`cd /home/ubuntu/OKN-WOBD/`

- Pull the latest changes from the repo as needed:
`git pull origin main`

- Navigate to the web app directory:
`cd /home/ubuntu/OKN-WOBD/web-v2`

- Add new npm modules in /home/ubuntu/OKN-WOBD/web-v2 as:
`npm ci`

- Re-build the web site in /home/ubuntu/OKN-WOBD/web-v2 as:
`npm run build`

- Service management (preferred for production deployment):
```
sudo systemctl status okn-wobd-web
sudo systemctl restart okn-wobd-web
sudo journalctl -u okn-wobd-web -f
```

- Manual launch alternative (without systemd and not preferred for production deployment, stops when you close the SSH session (unless you detached)):
`npm start -- -p 3000`

### Docker (container image)

Build context is the `web-v2` directory. Use **one** of these:

**From the repository root** (paths are relative to the clone):

```
docker build -f web-v2/Dockerfile -t wobd-web-v2 web-v2
docker run --rm -p 3000:3000 wobd-web-v2
```

**From `web-v2/`** (same result; use this if your shell is already in that directory):

```
docker build -f Dockerfile -t wobd-web-v2 .
docker run --rm -p 3000:3000 wobd-web-v2
```

For **either** `docker run` above, `-e NEXT_PUBLIC_FRINK_FEDERATION_URL=<url>` is **optional**—add it only when you need to override the default FRINK federation URL (for example: `docker run --rm -p 3000:3000 -e NEXT_PUBLIC_FRINK_FEDERATION_URL=https://... wobd-web-v2`).

**Smoke test:** the image defaults to the **`/wobd`** subpath (`NEXT_PUBLIC_BASE_PATH=/wobd` at build time), so open **`http://localhost:3000/wobd`**, not the site root. If you run `docker build` from the wrong working directory, Docker will error with `path "web-v2" not found` when the final context argument is `web-v2` but that folder is not under the current directory.

Put the app behind a reverse proxy at `https://example.org/wobd` and forward that prefix to the container. To serve at the site root instead (e.g. local or dedicated host), rebuild with `--build-arg NEXT_PUBLIC_BASE_PATH=` (empty).

For non-Docker builds (e.g. `npm run build` on a server), set `NEXT_PUBLIC_BASE_PATH=/wobd` in the environment when building if the app is not at the origin root.

Pass any other production secrets and URLs with `-e` or your orchestrator’s environment configuration. The app listens on port 3000 inside the container (`HOSTNAME=0.0.0.0`).

### GitHub Actions → GHCR (container registry)

Official images are built in CI and pushed to **GitHub Container Registry** when a **GitHub Release is published** (not on every push to `main`).

**Workflow file:** [`.github/workflows/web-v2-ghcr.yml`](../../.github/workflows/web-v2-ghcr.yml) (repository root).

**When it runs**

- **Release published:** Someone publishes a **GitHub Release** (draft releases do not trigger this). Use a **semver tag** on the release, e.g. `v1.2.0` (leading `v` is normal).
- **Workflow dispatch:** In the repo → **Actions** → select **“Build and push web-v2 to GHCR”** → **Run workflow**. Useful for ad-hoc verification builds. The image is still tagged with a **`sha-*`** digest; **`latest` is not updated** on manual runs.

**Image name**

- `ghcr.io/<lowercase-owner>/<lowercase-repo>` — for example `ghcr.io/sulab/okn-wobd` for repository `SuLab/OKN-WOBD`.

**Tags produced**

- **Semver:** e.g. `1.2.0` and `1.2` derived from tag `v1.2.0`.
- **`sha-*`:** identifies the exact Git commit built.
- **`latest`:** updated only when a **stable** release is published (not a **pre-release**). Pre-releases still get semver-style tags but do not move `latest`.

**Repository / organization setup**

- **Actions** must be allowed for the repository.
- Under **Settings → Actions → General → Workflow permissions**, the default `GITHUB_TOKEN` must be able to publish packages (often **“Read and write permissions”** at the repo level, or your org’s equivalent policy).
- If pushes to GHCR fail with **403**, an **organization owner** may need to adjust **org Settings** for **Actions** or **Packages**.

#### Steps to create a tagged release and publish the image

1. Merge and verify the code you intend to ship (for example on `main`).
2. **Create the Git tag** (semver), on the correct commit:
   - **Git CLI:**  
     `git tag -a v1.2.0 -m "web-v2 1.2.0"`  
     `git push origin v1.2.0`
   - **GitHub UI:** You can also create the tag while drafting the release (step 3).
3. **Publish a GitHub Release:** Repo → **Releases** → **Draft a new release** → choose the tag `v1.2.0` (create it here if it does not exist yet) → add release title/notes → **Publish release** (not “Save draft”). That event **starts the workflow automatically**—you do not need to trigger it by hand.
4. **Confirm CI:** **Actions** → open the **Build and push web-v2 to GHCR** run kicked off by that release; ensure it completes without errors. **Optional:** to exercise the same workflow without publishing a release, use **Actions** → that workflow → **Run workflow** (manual runs produce a `sha-*` image tag and do **not** move `latest`; see **When it runs** above).
5. **Pull on the server (or locally):**  
   `docker pull ghcr.io/<owner>/<repo>:1.2.0`  
   or `:latest` after a **stable** (non–pre-release) publish. Authenticate to GHCR if the package is private:  
   `echo <TOKEN> | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin`  
   (token needs at least `read:packages`; authorize SSO for the org if required).

**Note:** Pushing only a git tag **without** publishing a GitHub Release does **not** run this workflow. The intended gate is **Publish release**.

### Optional: `OKN_SPARQL_LOG` (template query diagnostics)

Use on **Docker, Kubernetes, EC2 + systemd**, **local dev**, or any host—the variable must reach the **Next.js server** process (`1`, `true`, or `yes`).

**Examples**

- **Local dev:** `OKN_SPARQL_LOG=1 npm run dev` — structured lines print in that terminal.
- **Built app:** `OKN_SPARQL_LOG=1 npm start` — match your deployed env (e.g. `NEXT_PUBLIC_BASE_PATH=/wobd npm start` if you use the `/wobd` subpath).
- **Docker:** add `-e OKN_SPARQL_LOG=1` to `docker run` next to any other `-e` flags.
- **systemd / EC2:** `Environment="OKN_SPARQL_LOG=1"` (or equivalent) in the unit file.
- **`web-v2/.env.local`:** optional line `OKN_SPARQL_LOG=1` so `next dev` / `npm start` pick it up without prefixing the command.

Output goes to **process logs** (that terminal, **`journalctl -u …`**, **`docker logs <container>`**).

When set, each **dashboard template** run that calls `POST /api/tools/sparql/execute` prints one **JSON line** to the process log (e.g. `journalctl`, `docker logs`). The line includes `template_task`, `run_id`, federation `endpoint`, timeouts, first- and second-attempt latencies (if a repair retry runs), repair metadata, row count, and a short **SHA-256 fingerprint** of the query—not the full SPARQL string. **`POST /api/tools/drug-datasets`** emits additional **`drug_datasets_*`** structured lines (`drug_datasets_pipeline_post_plan`, `drug_datasets_post_augment`, exceptions) covering requested drugs, per-step federation latencies, failed step ids, pipeline outcome, row counts around GXA augment, etc. Executor-driven SPARQL steps also send **`template_task`** (`drug_datasets:step2:raw_sparql`, …, or **`query_plan:…`** for chat multi-hop) so federation attempts appear in **`template_sparql_execute`** lines the same way. Chat-only callers that omit a prefix still get `query_plan:…`; omit the variable entirely if you do not need telemetry.

