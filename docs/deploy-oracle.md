# Deploy on Oracle Cloud Always Free (one VM, all your apps)

Result: a free ARM server (2 CPU / 12 GB RAM on new accounts) running this project and your other projects
side by side, each at its own HTTPS subdomain, e.g. `https://decision.ahmed.duckdns.org`. It is always on, with no sleeping.

Takes about 45 minutes the first time. You need a credit or debit card for identity verification. Oracle places a small
temporary hold and doesn't charge an Always Free account.

---

## 1. Create the account

1. Go to **oracle.com/cloud/free** → *Start for free*.
2. **Home region: choose carefully, it can't be changed later.** Free ARM capacity varies by region. For the Gulf,
   *UAE East (Dubai)*, *Saudi Arabia West (Jeddah)* or *Germany Central (Frankfurt)* are good choices.
3. Finish the card verification and wait for the "account ready" email (minutes to a few hours).

## 2. Create the VM

Console → **☰ → Compute → Instances → Create instance**

| Setting | Value |
|---|---|
| Name | `apps` |
| Image | **Canonical Ubuntu 24.04** (click *Change image*) |
| Shape | *Change shape* → **Ampere** → `VM.Standard.A1.Flex` → **2 OCPU, 12 GB** (the full free allowance) |
| Networking | *Create new virtual cloud network* + *public subnet*; **Assign a public IPv4 address: yes** |
| SSH keys | **Generate a key pair for me** → *Save private key* (keep this `.key` file safe; you can't download it again) |
| Boot volume | default (≈47 GB; up to 200 GB is free) |

Click **Create**. When it shows *Running*, copy the **Public IP address**.

> **"Out of capacity for shape VM.Standard.A1.Flex"** is common on free accounts. Try another *Availability
> domain* in the same screen, try again later (early morning UTC works best), or try 1 OCPU / 6 GB first and
> resize later. Upgrading the account to *Pay As You Go* removes the capacity problem. You still pay nothing
> while you stay inside the Always Free limits, but anything above them is billed, so set a budget alert first.

## 3. Open ports 80 and 443 in Oracle's network firewall

Instance page → **Primary VNIC → Subnet → Security Lists → Default Security List → Add Ingress Rules**.
Add two rules:

| Source CIDR | IP protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(Port 22 for SSH is already open. The VM also has its own firewall, which `setup.sh` opens in step 6.)

## 4. Get a free domain name

Caddy needs a domain to get HTTPS certificates. Any one of these works:

- **DuckDNS (fastest, free):** sign in at duckdns.org, create e.g. `ahmed` and paste the VM's public IP.
  Every subdomain of it (`decision.ahmed.duckdns.org`, `project2.ahmed.duckdns.org`) resolves to your VM automatically.
- **GitHub Student Pack:** includes a free domain for a year from its domain partners. Add an **A record** for `*`
  (wildcard) and one for `@`, both pointing at the VM's public IP.

## 5. Connect over SSH (Windows PowerShell)

```powershell
icacls "$HOME\Downloads\ssh-key.key" /inheritance:r /grant:r "$($env:USERNAME):R"
ssh -i "$HOME\Downloads\ssh-key.key" ubuntu@<PUBLIC_IP>
```

## 6. Bootstrap the server (one command)

On the server:

```bash
curl -fsSL https://raw.githubusercontent.com/AhmedSAAhmed/The-Decision-Engine/main/deploy/oracle/setup.sh -o setup.sh
bash setup.sh
```

It installs Docker, opens ports 80/443 in the VM firewall, adds 2 GB swap, clones this repo into `/opt/apps`,
and copies the Compose file, Caddyfile and `.env` template next to it. Then **log out and SSH back in**.

## 7. Configure and start

```bash
nano /opt/apps/.env          # DOMAIN=ahmed.duckdns.org   EMAIL=you@...   (API keys optional)
cd /opt/apps
docker compose up -d --build
docker compose logs -f caddy # wait for "certificate obtained successfully", then Ctrl+C
```

Open `https://decision.<your DOMAIN>`. Health check: `https://decision.<your DOMAIN>/api/health`.

## 8. Add your other projects

For each project:

1. `cd /opt/apps && git clone <repo-url> project-2` (the project needs a `Dockerfile`; copy this repo's as a starting point).
2. In `docker-compose.yml`, uncomment and adapt the `project-2` service.
3. In `Caddyfile`, add a block: `project2.{$DOMAIN} { reverse_proxy project-2:<its port> }`
4. `docker compose up -d --build`

12 GB RAM comfortably fits eight small Python apps (this one uses about 150 MB; each has a 768 MB cap).

## 9. Updating after a git push

```bash
cd /opt/apps/The-Decision-Engine && git pull
cd /opt/apps && docker compose up -d --build decision-engine
```

The audit log lives in the `decision_runs` Docker volume, so it survives restarts and redeploys.

## Keep it free and alive

- **Idle reclamation:** Oracle may reclaim an Always Free VM that is idle for 7 days (very low CPU, network
  and memory use). Eight live apps usually keep it busy. A Pay-As-You-Go account isn't reclaimed.
- Stay within **2 OCPU / 12 GB** of ARM capacity and 200 GB of total block storage.
- Set **Billing → Budgets** to alert at $1 if you upgrade to Pay As You Go.
- Back up anything important; free-tier VMs have no SLA.
