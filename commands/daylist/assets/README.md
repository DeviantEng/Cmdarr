# Daylist Assets (from Meloday)

Assets bundled from [Meloday](https://github.com/trackstacker/meloday) for the Cmdarr daylist command.

## moodmap.json (required)

Maps Plex Sonic Analysis mood names to creative descriptor variants for playlist titles.
Example: "Cheerful" → ["Sunny", "Happy", "Upbeat", "Chirpy", "Breezy"]

**Critical for daylist functionality** – without this file, playlist titles fall back to generic descriptors.

## covers/flat/ (required for cover upload)

Time-of-day cover images for playlist posters. The daylist command applies the playlist title as text overlay and uploads via Plex HTTP API (requires Pillow).
- dawn_blank.webp, early-morning_blank.webp, morning_blank.webp, afternoon_blank.webp
- evening_blank.webp, night_blank.webp, late-night_blank.webp

## fonts/ (optional, for cover text overlay)

Meloday bundles Circular/Circular-Bold.ttf for cover text. Cmdarr includes the same font from Meloday.
The daylist command tries the bundled font first, then falls back to system fonts (Helvetica, DejaVu, Liberation).
Note: Circular is a commercial font; Meloday includes it in their repo. Use at your own discretion.
