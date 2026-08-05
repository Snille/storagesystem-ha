const CARD_VERSION = "1.0.2";

const STRINGS = {
  en: {
    title: "Storage Search",
    placeholder: "Search for something",
    search: "Search",
    microphone: "Microphone",
    stop: "Stop",
    location: "Location",
    summary: "Summary",
    imageAlt: "Match image",
    noAnswer: "No answer yet.",
    listening: "Listening...",
    notSupported: "Speech recognition is not available in this browser.",
    failed: "Search failed.",
    openImage: "Open image",
    source: "Source",
    matches: "Matches"
  },
  sv: {
    title: "Lagersök",
    placeholder: "Sök efter något i verkstan",
    search: "Sök",
    microphone: "Mikrofon",
    stop: "Stoppa",
    location: "Plats",
    summary: "Sammanfattning",
    imageAlt: "Träffbild",
    noAnswer: "Inget svar ännu.",
    listening: "Lyssnar...",
    notSupported: "Taligenkänning stöds inte i den här webbläsaren.",
    failed: "Sökningen misslyckades.",
    openImage: "Öppna bild",
    source: "Källa",
    matches: "Träffar"
  },
  de: {
    title: "Lagersuche",
    placeholder: "Suche nach etwas",
    search: "Suchen",
    microphone: "Mikrofon",
    stop: "Stopp",
    location: "Ort",
    summary: "Zusammenfassung",
    imageAlt: "Trefferbild",
    noAnswer: "Noch keine Antwort.",
    listening: "Höre zu...",
    notSupported: "Spracherkennung wird in diesem Browser nicht unterstützt.",
    failed: "Suche fehlgeschlagen.",
    openImage: "Bild öffnen",
    source: "Quelle",
    matches: "Treffer"
  }
};

const SPEECH_LOCALES = { en: "en-US", sv: "sv-SE", de: "de-DE" };

class StorageSystemSearchCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:storagesystem-search-card",
      title: "Storage Search",
      language: "en",
      microphone_uses_ask: true
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._query = "";
    this._loading = false;
    this._error = "";
    this._listening = false;
    this._recognition = null;
    this._result = null;
    this._speechSupported =
      typeof window !== "undefined" &&
      Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  }

  setConfig(config) {
    this._config = {
      title: "",
      language: "en",
      // Text input uses the plain search endpoint; the microphone uses the
      // AI-backed ask endpoint, which also triggers TTS when it is enabled.
      microphone_uses_ask: true,
      limit: 5,
      // Only needed when several Storage System instances are configured.
      config_entry_id: null,
      // Fallback source when a service call cannot return a response.
      entity_prefix: "sensor.storage_system",
      ...config
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const active = this.shadowRoot?.activeElement;
    if (active && active.id === "query") {
      return;
    }
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _strings() {
    return STRINGS[this._config?.language] || STRINGS.en;
  }

  _escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /**
   * Map translation_key -> entity_id for this integration.
   *
   * Entity ids are derived from the *translated* entity name, so they differ
   * per Home Assistant language (sensor.storage_system_senaste_svar on a
   * Swedish instance, ..._latest_answer on an English one). Resolving through
   * the entity registry keeps the card working in any language.
   */
  _entityMap() {
    const registry = this._hass?.entities;
    if (!registry) {
      return null;
    }

    const map = {};
    for (const entry of Object.values(registry)) {
      const platform = entry.platform ?? entry.pl;
      const key = entry.translation_key ?? entry.tk;
      const entityId = entry.entity_id ?? entry.ei;
      if (platform === "storagesystem" && key && entityId) {
        map[key] = entityId;
      }
    }
    return Object.keys(map).length ? map : null;
  }

  _entityValue(key) {
    const map = this._entityMap();
    // Falls back to the English-named ids when the registry is unavailable.
    const entityId = map ? map[key] : `${this._config.entity_prefix}_${key}`;
    const state = entityId ? this._hass?.states?.[entityId] : undefined;
    if (!state || ["unknown", "unavailable", ""].includes(state.state)) {
      return "";
    }
    return state.attributes?.full_value || state.state;
  }

  /** Read the last result from the integration's sensors. */
  _resultFromEntities() {
    return {
      answer: this._entityValue("latest_answer"),
      label: this._entityValue("latest_label"),
      location: this._entityValue("latest_location"),
      summary: this._entityValue("latest_summary"),
      thumbnail_url: this._entityValue("latest_thumbnail_url"),
      original_url: this._entityValue("latest_original_url"),
      source: this._entityValue("latest_source"),
      match_count: this._entityValue("latest_match_count")
    };
  }

  async _call(service, query) {
    if (!this._hass || !query.trim()) {
      return;
    }

    this._loading = true;
    this._error = "";
    this._render();

    const data = { query: query.trim() };
    if (service === "search") {
      data.limit = this._config.limit;
    }
    if (this._config.config_entry_id) {
      data.config_entry_id = this._config.config_entry_id;
    }

    try {
      const response = await this._hass.callService(
        "storagesystem",
        service,
        data,
        undefined,
        false,
        true
      );
      this._result = response?.response ?? null;
    } catch (error) {
      this._result = null;
      this._error = error?.message || this._strings().failed;
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _submitText() {
    await this._call("search", this._query);
  }

  async _submitVoice(query) {
    await this._call(this._config.microphone_uses_ask ? "ask" : "search", query);
  }

  _toggleListening() {
    const strings = this._strings();

    if (!this._speechSupported) {
      this._error = strings.notSupported;
      this._render();
      return;
    }

    if (this._listening && this._recognition) {
      this._recognition.stop();
      return;
    }

    const RecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
    this._error = "";

    const recognition = new RecognitionCtor();
    recognition.lang = SPEECH_LOCALES[this._config.language] || SPEECH_LOCALES.en;
    recognition.continuous = false;
    recognition.interimResults = true;

    recognition.onstart = () => {
      this._listening = true;
      this._render();
    };

    recognition.onresult = (event) => {
      this._query = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? "")
        .join(" ")
        .trim();
      this._render();
    };

    recognition.onerror = () => {
      this._listening = false;
      this._recognition = null;
      this._error = strings.failed;
      this._render();
    };

    recognition.onend = async () => {
      const transcript = this._query.trim();
      this._listening = false;
      this._recognition = null;
      this._render();
      if (transcript) {
        await this._submitVoice(transcript);
      }
    };

    this._recognition = recognition;
    recognition.start();
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const previousInput = this.shadowRoot.getElementById("query");
    const hadFocus = previousInput && this.shadowRoot.activeElement === previousInput;
    const selectionStart = hadFocus ? previousInput.selectionStart ?? this._query.length : null;
    const selectionEnd = hadFocus ? previousInput.selectionEnd ?? this._query.length : null;

    const strings = this._strings();
    const result = this._result ?? this._resultFromEntities();
    const answer = result.answer || "";
    const label = result.label || "";
    const location = result.location || "";
    const summary = result.summary || "";
    const thumbnailUrl = result.thumbnail_url || "";
    const originalUrl = result.original_url || thumbnailUrl;
    const source = result.source || "";
    const matchCount = result.match_count ?? "";
    const disabledAttr = this._loading ? "disabled" : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          padding: 16px;
          background:
            radial-gradient(circle at top left, rgba(148, 214, 97, 0.18), transparent 34%),
            linear-gradient(145deg, rgba(28, 34, 28, 0.98), rgba(19, 25, 22, 0.98));
          color: var(--primary-text-color);
        }
        .title { font-size: 1.15rem; font-weight: 700; margin-bottom: 12px; }
        .controls {
          display: grid;
          grid-template-columns: 1fr auto auto;
          gap: 10px;
          align-items: center;
        }
        input {
          width: 100%;
          box-sizing: border-box;
          border-radius: 14px;
          border: 1px solid rgba(255,255,255,0.12);
          background: rgba(255,255,255,0.04);
          color: inherit;
          padding: 12px 14px;
          font: inherit;
        }
        button {
          border: 0;
          border-radius: 14px;
          padding: 11px 14px;
          font: inherit;
          font-weight: 600;
          cursor: pointer;
          color: #0d160f;
          background: #94d661;
        }
        button.secondary { background: rgba(255,255,255,0.08); color: inherit; }
        button:disabled { opacity: 0.6; cursor: default; }
        .status {
          margin-top: 10px;
          min-height: 1.2em;
          color: var(--secondary-text-color);
          font-size: 0.92rem;
        }
        .error { color: #ff9f9f; }
        .result { margin-top: 14px; display: grid; gap: 12px; }
        .meta { display: flex; flex-wrap: wrap; gap: 8px; }
        .pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          border-radius: 999px;
          padding: 6px 10px;
          background: rgba(255,255,255,0.08);
          color: var(--secondary-text-color);
          font-size: 0.85rem;
        }
        .body {
          display: grid;
          grid-template-columns: ${thumbnailUrl ? "112px 1fr" : "1fr"};
          gap: 14px;
          align-items: start;
        }
        .image-wrap { display: grid; gap: 8px; }
        img {
          width: 112px;
          height: 112px;
          object-fit: cover;
          border-radius: 16px;
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(255,255,255,0.08);
        }
        a.image-link { color: var(--primary-color); text-decoration: none; font-size: 0.9rem; }
        .answer { font-size: 1rem; line-height: 1.45; font-weight: 600; }
        .line { color: var(--secondary-text-color); line-height: 1.45; }
        .label { color: var(--primary-text-color); font-weight: 700; }
        @media (max-width: 480px) {
          .controls { grid-template-columns: 1fr; }
          .body { grid-template-columns: 1fr; }
          img { width: 100%; height: auto; aspect-ratio: 1 / 1; }
        }
      </style>
      <ha-card>
        <div class="title">${this._escapeHtml(this._config.title || strings.title)}</div>
        <div class="controls">
          <input id="query" type="text" placeholder="${strings.placeholder}"
            value="${this._escapeHtml(this._query)}" />
          <button id="search" ${disabledAttr}>${this._loading ? "..." : strings.search}</button>
          <button id="voice" class="secondary" ${disabledAttr}>
            ${this._listening ? strings.stop : strings.microphone}
          </button>
        </div>
        <div class="status ${this._error ? "error" : ""}">
          ${this._escapeHtml(this._error || (this._listening ? strings.listening : ""))}
        </div>
        <div class="result">
          <div class="meta">
            ${source ? `<span class="pill">${strings.source}: ${this._escapeHtml(source)}</span>` : ""}
            ${matchCount !== "" ? `<span class="pill">${strings.matches}: ${this._escapeHtml(matchCount)}</span>` : ""}
          </div>
          <div class="body">
            ${
              thumbnailUrl
                ? `<div class="image-wrap">
                     <img src="${this._escapeHtml(thumbnailUrl)}" alt="${strings.imageAlt}">
                     ${originalUrl ? `<a class="image-link" href="${this._escapeHtml(originalUrl)}" target="_blank" rel="noreferrer">${strings.openImage}</a>` : ""}
                   </div>`
                : ""
            }
            <div>
              <div class="answer">${this._escapeHtml(answer || strings.noAnswer)}</div>
              ${label ? `<div class="line"><span class="label">${this._escapeHtml(label)}</span></div>` : ""}
              ${location ? `<div class="line">${strings.location}: ${this._escapeHtml(location)}</div>` : ""}
              ${summary ? `<div class="line">${strings.summary}: ${this._escapeHtml(summary)}</div>` : ""}
            </div>
          </div>
        </div>
      </ha-card>
    `;

    const queryInput = this.shadowRoot.getElementById("query");

    queryInput?.addEventListener("input", (event) => {
      this._query = event.target.value;
    });

    queryInput?.addEventListener("keydown", async (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        await this._submitText();
      }
    });

    this.shadowRoot.getElementById("search")?.addEventListener("click", async () => {
      await this._submitText();
    });

    this.shadowRoot.getElementById("voice")?.addEventListener("click", () => {
      this._toggleListening();
    });

    if (hadFocus && queryInput) {
      queryInput.focus();
      if (selectionStart !== null && selectionEnd !== null) {
        queryInput.setSelectionRange(selectionStart, selectionEnd);
      }
    }
  }
}

if (!customElements.get("storagesystem-search-card")) {
  customElements.define("storagesystem-search-card", StorageSystemSearchCard);

  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "storagesystem-search-card",
    name: "Storage System Search Card",
    description: "Search the storage system with text or microphone and show answer, image, and location.",
    preview: false
  });

  console.info(`%c STORAGESYSTEM-SEARCH-CARD %c ${CARD_VERSION} `,
    "color:#0d160f;background:#94d661;font-weight:700",
    "color:#94d661;background:#0d160f");
}
