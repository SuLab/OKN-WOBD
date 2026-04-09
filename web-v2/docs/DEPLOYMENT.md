## WOBD Deployment Instructions

These instructions are for deployment of the web app (code within the web-v2 directory) to an AWS EC2 instance.

### Steps to run on localhost
- On localhost, run `cd web-v2 && npm run build` (Note: stop the app on localhost if still running under `npm run dev`)

- Run a smoke-test of the built app locally:
`cd web-v2 && npm run build && npm start`

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

