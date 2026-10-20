import QtQuick

// Przełącznik 0/1 (makieta: .tog). Klik zmienia wartość od razu (`toggled`); `tryClick()` to jedyna ścieżka kliknięcia (mysz i scenariusz testowy).
Rectangle {
  id: sw

  property bool on: false
  property bool active: true

  signal toggled(bool value)

  function tryClick() { if (active) toggled(!on) }

  implicitWidth: 40
  implicitHeight: 22
  radius: 11
  color: on ? Theme.alpha(Theme.ok, 0.38) : Theme.line2
  border.width: 1
  border.color: on ? Theme.alpha(Theme.ok, 0.7) : Theme.line
  opacity: active ? 1 : 0.5

  Rectangle {
    width: 16
    height: 16
    radius: 8
    y: 3
    x: sw.on ? sw.width - width - 3 : 3
    color: sw.on ? Theme.ok : Theme.dim
    Behavior on x { NumberAnimation { duration: 110 } }
  }

  MouseArea {
    anchors.fill: parent
    cursorShape: sw.active ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: sw.tryClick()
  }
}
