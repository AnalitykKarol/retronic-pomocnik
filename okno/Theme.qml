pragma Singleton
import QtQuick

// Tokeny okna Retronic: Tokyo Night, JetBrains Mono (ze wspolne.css makiet specs/makiety-okno-1019). Okno jest osobnym
// procesem Quickshella, więc nie ma motywu Omarchy (qs.Commons) jak pasek: kolory są tutaj, w jednym miejscu.
QtObject {
  readonly property color bg: "#1a1b26"
  readonly property color bg2: "#16161e"
  readonly property color sur: "#1f2335"
  readonly property color sur2: "#24283b"
  readonly property color line: "#2f3549"
  readonly property color line2: "#414868"
  readonly property color fg: "#c0caf5"
  readonly property color fg2: "#a9b1d6"
  readonly property color dim: "#737aa2"
  readonly property color dim2: "#565f89"
  readonly property color ok: "#6fbf73"
  readonly property color warn: "#d9a441"
  readonly property color bad: "#f7768e"
  readonly property color blue: "#7aa2f7"
  readonly property color cyan: "#7dcfff"
  readonly property color mag: "#bb9af7"

  readonly property string font: "JetBrainsMono Nerd Font"
  readonly property int body: 13        // makieta 12.5 px
  readonly property int small: 11       // 11-11.5 px
  readonly property int tiny: 10        // 10-10.5 px (etykiety wersalikami)
  readonly property int title: 16

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  // ton ("ok", "warn", "bad", "blue", "mag", "cyan", "fg", "fg2", "dim", "dim2") -> kolor
  function tone(name) {
    if (name === "ok") return ok
    if (name === "warn") return warn
    if (name === "bad" || name === "stop") return bad
    if (name === "blue") return blue
    if (name === "mag") return mag
    if (name === "cyan") return cyan        // stan „Karol gra” (Przegląd): to nie awaria, więc nigdy bad/warn
    if (name === "fg") return fg
    if (name === "fg2") return fg2
    if (name === "dim2") return dim2
    return dim
  }

  // klasa panel.py -> kolor kropki jak na pasku: dziala zielony, stop bursztyn, alarm czerwony, brak szary
  function stateColor(klasa) {
    if (klasa === "alarm") return bad
    if (klasa === "dziala") return ok
    if (klasa === "stop") return warn
    return dim2
  }
}
