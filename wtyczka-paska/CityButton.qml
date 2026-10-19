import QtQuick
import qs.Commons

// Mały przycisk akcji miasta ("⌂ Miasto", "↻ Refill"): ten sam język co Stop/Start (kolor akcentu, obrys, 26 px).
// Szary przycisk też zgłasza najechanie myszą, żeby panel mógł pokazać powód (`spec.hint`) pod wierszem.
// Klika się tylko myszą (Enter/Spacja go nie wciskają). `spec` to wynik Model.returnButton / Model.refillButton.
Rectangle {
  id: button

  property var spec: ({ action: "", label: "", enabled: false, hint: "", tone: "off" })
  property bool busy: false
  property color foreground: Color.foreground
  property color urgent: Color.urgent
  property color okColor: "#6fbf73"
  property color warnColor: "#d9a441"
  property string fontFamily: Style.font.family

  readonly property bool canClick: spec.enabled && !busy
  readonly property bool hovered: mouse.containsMouse
  readonly property color accent: spec.tone === "stop" ? urgent : (spec.tone === "warn" ? warnColor : okColor)
  readonly property color dim: Qt.darker(foreground, 1.55)

  signal activated()

  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  width: Style.space(96)
  height: Style.space(26)
  radius: Style.cornerRadius
  color: canClick ? alpha(accent, hovered ? 0.30 : 0.16) : "transparent"
  border.width: 1
  border.color: canClick ? accent : alpha(foreground, 0.2)

  Text {
    anchors.centerIn: parent
    text: button.busy ? "…" : button.spec.label
    color: button.canClick ? button.accent : button.dim
    font.family: button.fontFamily
    font.pixelSize: Style.font.bodySmall
    font.bold: true
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: button.canClick ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: if (button.canClick) button.activated()
  }
}
