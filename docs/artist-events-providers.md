# Artist event providers

Cmdarr aggregates upcoming shows from optional external APIs. **Ticketmaster Discovery** is the only source with reliable self-serve API access for new deployments.

## Ticketmaster Discovery (recommended)

- **Registration:** Open — [developer.ticketmaster.com](https://developer.ticketmaster.com/)
- **Auth:** `apikey` query param (Consumer Key from the developer portal)
- **Coverage:** US music events; keyword search + attraction metadata
- **Cmdarr notes:** Multi-artist bills match per attraction (name phrase + optional MusicBrainz ID on that attraction only). Co-headliner MBIDs do not block openers.

## Songkick (legacy / partner-only)

- **Registration:** Closed for new hobbyist/student keys; [Songkick states](https://www.songkick.com/api_key_requests/new) they are not processing new applications while improving the API.
- **Commercial use:** Requires partnership agreement and license fee ([inquiry form](https://support.songkick.com/hc/en-us/requests/new?ticket_form_id=360000526113)).
- **Cmdarr:** Client remains for deployments with an existing key. Not recommended for new setups.

## Bandsintown (legacy / partner-only)

- **Registration:** [Partner approval required](https://corp.bandsintown.com/data-applications-terms); intended for artists/enterprises, not general third-party apps.
- **Public `app_id`:** Historically any string worked for the REST API; newer access is restricted and may return 403 without partner approval.
- **Cmdarr:** Client remains for deployments with a working `app_id`. Not recommended for new setups.

## Alternatives considered (not implemented)

| Option | Notes |
|--------|--------|
| **SeatGeek API** | Partner/commercial; similar barriers to Songkick |
| **AXS / Eventbrite** | Limited or partner-gated event APIs |
| **Web scraping** | Fragile, ToS risk, high maintenance; avoided for now |
| **Setlist.fm** | Set lists, not upcoming ticketed shows |

If Songkick and Bandsintown are removed in a future release, existing `concert_event_source` rows for those providers would remain historical only; new ingests would be Ticketmaster-only.
