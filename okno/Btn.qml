import QtQuick

// Przycisk okna (jak .btn w makiecie). Klika się tylko myszą; `tryClick()` to jedyna ścieżka kliknięcia (MouseArea i scenariusz
// testowy), więc szarość i blokada obowiązują wszędzie tak samo. Szary przycisk też zgłasza najechanie (`hovered`), żeby
// widok pokazał powód (`hint`).
Rectangle {
  id: btn

  property string label: ""
  property string tone: "neutral"        // neutral | ok | stop | warn | prim
  property bool active: true
  property bool busy: false
  property string hint: ""
  property bool compact: false

  readonly property bool canClick: active && !busy
  readonly property bool hovered: mouse.containsMouse
  readonly property color accent: tone === "prim" ? Theme.blue : (tone === "neutral" ? Theme.fg2 : Theme.tone(tone))

  signal activated()

  function tryClick() { if (canClick) activated() }

  implicitWidth: Math.max(compact ? 40 : 60, text.implicitWidth + (compact ? 16 : 24))
  implicitHeight: compact ? 26 : 28
  radius: 6
  border.width: 1
  border.color: !canClick ? Theme.line : (tone === "neutral" ? (hovered ? Theme.dim : Theme.line2) : accent)
  color: {
    if (!canClick) return "transparent"
    if (tone === "prim") return hovered ? Qt.lighter(Theme.blue, 1.1) : Theme.blue
    if (tone === "neutral") return hovered ? Theme.sur2 : "transparent"
    return Theme.alpha(accent, hovered ? 0.26 : 0.14)
  }

  Text {
    id: text
    anchors.centerIn: parent
    width: Math.min(implicitWidth, btn.width - 8)
    horizontalAlignment: Text.AlignHCenter
    text: btn.busy ? "…" : btn.label
    color: !btn.canClick ? Theme.dim2 : (btn.tone === "prim" ? Theme.bg : btn.accent)
    font.family: Theme.font
    font.pixelSize: Theme.small
    font.bold: true
    elide: Text.ElideRight
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: btn.canClick ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: btn.tryClick()
  }
}
