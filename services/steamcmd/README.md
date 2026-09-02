# steamcmd (Docker)

Headless management of Wallpaper Engine (app id 431960) using the [cm2network/steamcmd](https://hub.docker.com/r/cm2network/steamcmd) image, replacing the Steam desktop client. Downloads land in `~/.local/share/wallpaper_engine` (point waywallen's WE plugin there).

Both services are one-shot tools (`run --rm`) and both live under a profile, so a bare `docker compose up` won't accidentally start anything.

## 下载 / 更新壁纸（profile: wallpaper）

Interactive (paste a Workshop link directly; the number after `?id=` is extracted automatically):

```bash
./wallpaper.sh
```

Or pass the id via an environment variable:

```bash
WALLPAPER_ID=3608026357 docker compose --profile wallpaper run --rm wallpaper
```

The command is inlined in the compose file (`command:`); the wallpaper id comes from `WALLPAPER_ID` and the username defaults to `${STEAM_USER:-cloudmapleleaf}`. If the id is missing, compose rejects the run with a hint. Wallpapers land in `~/.local/share/wallpaper_engine/steamapps/workshop/content/431960/<ID>/`; to update, rerun the same command.

## 同步订阅与 WE 本体（profile: sync）

Subscribe to the wallpapers you want on the [Workshop web page](https://steamcommunity.com/app/431960/workshop/), then sync locally with one command:

```bash
docker compose --profile sync up
```

It syncs all Workshop content your account is subscribed to (new subscriptions are downloaded, existing ones skipped) and also updates the WE app itself (the shared effects / materials / shaders in `assets/`, which `scene.pkg` rendering depends on). Unsubscribing does not delete local files; delete the item directory manually when you want to clean up.

The command is inlined in the compose file (`command:`); the username defaults to `${STEAM_USER:-cloudmapleleaf}` — switch accounts with `STEAM_USER=xxx docker compose --profile sync up`. After starting, enter your Steam password when prompted (Steam Guard is cached in the `steam-home` volume, so no more verification codes); the container exits on its own when done, and leaving it around is fine — the next `up` recreates it.

(`@sSteamCmdForcePlatformType windows` is required: WE has no Linux depot.)

Assets land in `~/.local/share/wallpaper_engine/steamapps/common/wallpaper_engine/assets/`.

## 说明

- The first login asks for your password and a Steam Guard code; the Guard state is cached in the `steam-home` volume, so no repeat verification afterwards (the password is still asked each time).
- The `steam-home` named volume persists `/home/steam` inside the container (login cache, steamcmd self-updates). It is Docker-managed and unrelated to the host HOME.
- The in-container user is uid 1000, matching the host, so downloaded files are owned by your current user.
- To poke around inside the container: `docker compose --profile wallpaper run --rm --entrypoint bash wallpaper`.
