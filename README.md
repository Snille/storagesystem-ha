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

> **Entity ids follow your Home Assistant language.** They are generated from the
> translated entity name, so a Swedish instance gets
> `sensor.storage_system_senaste_svar` where an English one gets
> `sensor.storage_system_latest_answer`. The names below are the English ones — check
> the device page for the ids on your instance. The bundled card does not care: it
> resolves entities through the registry.

One device per instance, with:

- `binary_sensor.storage_system_api` — connectivity, attributes `base_url` and `service`
- `sensor.storage_system_api_timestamp` — when the API was first seen healthy in
  the current connected stretch. It deliberately does *not* follow the clock in
  every health payload: that changed on every poll and wrote a logbook entry and
  a recorder row per minute. It now only moves when the connection drops and
  comes back, so "unchanged for three days" means three days of uptime.
- `sensor.storage_system_latest_answer`, `_latest_query`, `_latest_location`,
  `_latest_box_id`, `_latest_label`, `_latest_source`, `_latest_summary`,
  `_latest_keywords`, `_latest_match_count`, `_latest_photo_count`,
  `_latest_thumbnail_url`, `_latest_original_url`
- disabled by default (enable them if you need them): `_latest_location_id`,
  `_latest_session_id`
- filed under Diagnostic on the device page: `_latest_thumbnail_url`,
  `_latest_original_url`

Every result sensor carries `query` and `mode` attributes, plus `full_value` when
the text was too long to fit in the state. States are kept short (asset URLs are
shown as `d716cc5f…/thumbnail`, longer text is cut at 100 characters) so they do
not wrap and push the entity names around in the device page — read `full_value`
in automations and templates when you need the complete text or URL.

The latest result is persisted, so the sensors and the card still show the last answer
after a Home Assistant restart rather than going blank.

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

## Voice: the conversation agent

The integration exposes `conversation.storage_system`, a stateless agent that forwards
**everything** said to it straight to `/api/public/ask` and returns the answer as speech.
Point an Assist pipeline at it and any satellite using that pipeline becomes a dedicated
storage-search kiosk — you just ask *"Where are the junction boxes?"*, with no wake prefix
and no sentence matching.

1. **Settings → Voice assistants → Add assistant**, set **Conversation agent → Storage
   System**, and pick your STT/TTS (e.g. Whisper and Piper).
2. Point the satellite's Assist pipeline setting at that pipeline.

Notes:

- Because the satellite speaks the answer itself, this path never uses the *Speak answers*
  option. Leave that **off** for voice satellites, or you get the answer twice.
- A satellite on this pipeline can no longer do normal HA voice control (lights, timers) —
  everything goes to storage. That's the point; use another device or pipeline for those.
- Voice queries update the same sensors and fire the same events as the services, so a
  dashboard stays in sync with what was asked by voice.
- Semicolons in answers are turned into periods, because most TTS engines barely pause on
  a semicolon and the answer comes out as one rushed run-on sentence.
- Turn the agent off entirely with the *Expose a conversation agent* option. The entity
  then goes `unavailable`; remove it from the entity registry if you want it gone.

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
| `entity_prefix` | `sensor.storage_system` | Last-resort id prefix, used only if the entity registry is unavailable. |

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
5. Point dashboard cards at the new `sensor.storage_system_*` entities instead of the
   old `input_text.lagersystem_*` ones. Check the device page for the exact ids — they
   follow your Home Assistant language.
6. Change the card type from `custom:lagersystem-search-card` to
   `custom:storagesystem-search-card`.

Automations that only listen for `lagersystem_result` need no changes.

### If you used the `verkstan_conversation` custom component

That hand-copied agent called `rest_command.lagersystem_ask` from the YAML package. It is
replaced by `conversation.storage_system`:

1. Enable *Expose a conversation agent* (on by default).
2. Repoint your Assist pipeline's conversation agent to **Storage System**. STT and TTS
   (Whisper/Piper) stay exactly as they are, and the satellite firmware needs no change.
3. Remove the integration entry, then delete `/config/custom_components/verkstan_conversation/`
   and restart.

If you used the prefix-word route instead (`custom_sentences/…/verkstan.yaml` plus an
`intent_script`), replace the `rest_command.lagersystem_ask` call in the `intent_script`
with `storagesystem.ask` and read the answer from the response instead of the helper:

```yaml
intent_script:
  VerkstanFraga:
    speech:
      text: "{{ answer_text }}"
    action:
      - action: storagesystem.ask
        data:
          query: "{{ query }}"
          speak: false
        response_variable: resp
      - variables:
          answer_text: >-
            {{ (resp.answer | default('') | regex_replace(';\s*', '. '))
               or 'Jag hittade inget tydligt svar.' }}
```

## Label printing

Deliberately not exposed. `/api/labels/print` is not part of the app's public
API and printing has real side effects, so it needs its own auth boundary in the
app before an integration should be allowed to trigger it.

## License

MIT — see [LICENSE](LICENSE).

[app-repo]: https://github.com/Snille/storagesystem
[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
