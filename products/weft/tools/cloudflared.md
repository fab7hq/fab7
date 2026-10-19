# Cloudflare Tunnel for Weft's Remote

Remote can reach this machine through a Cloudflare quick tunnel: no Cloudflare
account or domain. Weft starts `cloudflared` itself. You install it, on the
`PATH` Weft starts with, then press **Check** in Weft's Remote.

## macOS

```sh
brew install cloudflared
```

## Linux

Debian and Ubuntu:

```sh
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update && sudo apt-get install cloudflared
```

RHEL and CentOS:

```sh
curl -fsSL https://pkg.cloudflare.com/cloudflared.repo | sudo tee /etc/yum.repos.d/cloudflared.repo
sudo yum install cloudflared
```

Anything else: [Cloudflare's downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).

## Check

`cloudflared --version` answers in a terminal. Then **Check** in Remote.
Somewhere other than `PATH`: put its path in `~/.fab7/weft/config.toml`:

```toml
[remote]
program = "/path/to/cloudflared"
```

## What to know

- Traffic is decrypted at Cloudflare's edge.
- A quick tunnel's address changes each time it starts. Cloudflare means it
  for testing, with no uptime guarantee, and it answers 429 past 200 requests
  at once.
