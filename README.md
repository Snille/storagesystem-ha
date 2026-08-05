# Storage System — Home Assistant integration

[![hacs][hacs-badge]][hacs]

Home Assistant integration for [Storage System][app-repo], a workshop inventory
app with an AI-backed search API. It replaces the hand-copied YAML package that
used to live in the app repo under `deploy/`.

Compared to the YAML package this gives you:

- UI setup — no `secrets.yaml`, no `packages:` include, no restart to reconfigure
- real entities instead of `input_text` helpers, so the 255-character limit no
  longer truncates answers (the full text lands in a `full_value` attribute)
- two services instead of two 300-line scripts
- the Lovelace search card served by the integration itself, so there is nothing
  to copy into `/config/www` and no dashboard resource to register by hand

## Requirements

- Home Assistant 2024.12 or newer
- A reachable Storage System instance with a public base URL configured in
  `Settings -> Security -> Public base URL`
- Optionally an API key from `Settings -> Security` (strongly recommended if the
  app is reachable from the internet)

## Installation

### HACS

1. In HACS, open the three-dot menu and choose **Custom repositories**.
2. Add `https://github.com/Snille/storagesystem-ha` with category **Integration**.
3. Install **Storage System** and restart Home Assistant.

### Manual

Copy `custom_components/storagesystem` to `<config>/custom_components/` and
restart Home Assistant.

## Configuration

**Settings → Devices & Services → Add Integration → Storage System.**

| Field | Notes |
| --- | --- |
| Base URL | e.g. `https://lager.example.com`. Without `/api/public` — a pasted API path is stripped automatically. |
| API key | Matches `Settings -> Security` in the app, or `LAGERSYSTEM_API_KEY`. Leave empty if the app has no key. |

Options (the ⚙️ on the integration card):

| Option | Default | Notes |
| --- | --- | --- |
| Health check interval | 60 s | How often `/api/public/health` is polled. |
| Language | `en` | Used by the bundled search card (`en`, `sv`, `de`). |
| Speak answers | off | When on, `storagesystem.ask` reads the answer out loud. |
| TTS entity / media player | — | Required when *Speak answers* is on. |

If the API key is rotated in the app, Home Assistant raises a reauth prompt
instead of silently going offline.

## Entities

One device per instance, with:

- `binary_sensor.storage_system_api` — connectivity, attributes `base_url` and `service`
- `sensor.storage_system_api_timestamp` — timestamp from the last health poll
- `sensor.storage_system_latest_answer`, `_latest_query`, `_latest_location`,
  `_latest_box_id`, `_latest_label`, `_latest_source`, `_latest_summary`,
  `_latest_keywords`, `_latest_match_count`, `_latest_photo_count`,
  `_latest_thumbnail_url`, `_latest_original_url`
- disabled by default (enable them if you need them): `_latest_location_id`,
  `_latest_session_id`

Every result sensor carries `query` and `mode` attributes, plus `full_value` when
the text was too long to fit in the state.

## Services

### `storagesystem.ask`

Calls `/api/public/ask` for an AI-generated answer, updates the sensors, fires
the result event, and speaks the answer when that option is on.

```yaml
action: storagesystem.ask
data:
  query: Where are the junction boxes?
```

Fields: `query` (required), `speak`, `tts_entity`, `media_player`,
`config_entry_id` (only needed with more than one instance).

### `storagesystem.search`

Calls `/api/public/search` for structured matches without generating an answer.

```yaml
action: storagesystem.search
data:
  query: junction boxes
  limit: 5
```

Both services return their result, so a script can use it directly:

```yaml
- action: storagesystem.search
  data:
    query: junction boxes
  response_variable: hit
- action: notify.mobile_app
  data:
    message: "{{ hit.label }} is in {{ hit.location }}"
```

## Event

Every successful call fires `storagesystem_result` — and `lagersystem_result`
with identical data, so automations written against the old YAML package keep
working. The payload contains `query`, `answer`, `source`, `match_count`,
`box_id`, `label`, `location`, `location_id`, `session_id`, `summary`,
`keywords`, `photo_count`, `thumbnail_url`, `original_url`, `matches`, `mode`,
`error`, and `entry_id`.

```yaml
alias: Storage System - Forward Result
triggers:
  - trigger: event
    event_type: storagesystem_result
actions:
  - action: mqtt.publish
    data:
      topic: lagersystem/result
      payload: "{{ trigger.event.data | to_json }}"
mode: queued
```

## Search card

The card is registered automatically — add it to a dashboard with:

```yaml
type: custom:storagesystem-search-card
title: Lagersök
language: sv
microphone_uses_ask: true
```

| Card option | Default | Notes |
| --- | --- | --- |
| `title` | localized | Card heading. |
| `language` | `en` | `en`, `sv`, or `de`. Also sets the speech-recognition locale. |
| `microphone_uses_ask` | `true` | Microphone queries use `ask` (AI answer + TTS); typed queries always use `search`. |
| `limit` | `5` | Match limit for `search`. |
| `config_entry_id` | — | Only needed with more than one instance. |
| `entity_prefix` | `sensor.storage_system` | Fallback source when a service response is unavailable. |

Microphone input uses the browser's Web Speech API, which in practice means
Chrome or Edge over HTTPS.

## Migrating from the YAML package

1. Install the integration and add it through the UI.
2. Delete `/config/packages/lagersystem/` (or whatever you named it) and the
   `lagersystem_*` entries in `secrets.yaml`.
3. Remove `/config/www/lagersystem/home-assistant-search-card.js` and its
   dashboard resource entry.
4. Replace `script.lagersystem_fraga` → `storagesystem.ask` and
   `script.lagersystem_sok` → `storagesystem.search` in your automations.
5. Point dashboard cards at `sensor.storage_system_*` instead of the old
   `input_text.lagersystem_*` and `sensor.lagersystem_latest_*` entities.
6. Change the card type from `custom:lagersystem-search-card` to
   `custom:storagesystem-search-card`.

Automations that only listen for `lagersystem_result` need no changes.

## Label printing

Deliberately not exposed. `/api/labels/print` is not part of the app's public
API and printing has real side effects, so it needs its own auth boundary in the
app before an integration should be allowed to trigger it.

## License

MIT — see [LICENSE](LICENSE).

[app-repo]: https://github.com/Snille/storagesystem
[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
