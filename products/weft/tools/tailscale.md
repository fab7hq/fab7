# Tailscale Funnel for Weft's Remote

Remote can reach this machine through Tailscale Funnel, at its own stable
`https://<machine>.<tailnet>.ts.net` address; your phone needs no Tailscale
app. Weft starts `tailscale funnel` itself. You install Tailscale, sign in,
and have `tailscale` on the `PATH` Weft starts with, then press **Check** in
Weft's Remote.

## macOS

1. Install Tailscale's Standalone app, from
   [Tailscale's macOS install page](https://tailscale.com/kb/1016/install-mac) or with
   Homebrew:

   ```sh
   brew install --cask tailscale-app
   ```

2. Open it and sign in.
3. Put `tailscale` on your `PATH`: in the app's **Settings**, find **CLI
   integration**, choose **Show me how**, then **Install Now** (macOS 13 or
   later). It installs `/usr/local/bin/tailscale`.

The Mac App Store version keeps its command line inside the app, where Weft
cannot run it as one: install the Standalone app instead.

## Linux

```sh
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Weft runs `tailscale` as you, not as root: let your user operate Tailscale.

```sh
sudo tailscale set --operator=$USER
```

## Funnel

Funnel needs Tailscale 1.38.3 or later and MagicDNS on in your tailnet. The
first time Funnel runs, Tailscale asks you to approve it in the browser: Weft
shows Tailscale's own words and link under **Tunnel starting**. You can also
approve it ahead, in the admin console's **Access controls**: **Add Funnel to
policy**.

## Check

`tailscale version` answers in a terminal. Then **Check** in Remote.

## What to know

TLS ends on this machine; Tailscale's relay sees only the host name.
