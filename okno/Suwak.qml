import QtQuick
import "UstawieniaModel.js" as Ust

// Suwak pokrętła liczbowego (makieta: .slider). Podczas przeciągania pokazuje wartość tymczasową, a zapis (`committed`) idzie dopiero
// po puszczeniu myszy (Q3: "od razu po puszczeniu"). Zakres i krok z wpisu meta pokrętła (`knob`: min, max, typ), przyciąganie przez Ust.snap.
Item {
  id: sl

  property var knob: ({ min: 0, max: 1, typ: "calkowita" })
  property real value: 0
  property bool active: true

  property bool dragging: false
  property real dragValue: 0
  readonly property real shown: dragging ? dragValue : value
  readonly property real frac: knob.max > knob.min ? Math.max(0, Math.min(1, (shown - knob.min) / (knob.max - knob.min))) : 0

  signal committed(real value)

  implicitHeight: 22
  opacity: active ? 1 : 0.5

  function valueAt(x) {
    var f = Math.max(0, Math.min(1, x / Math.max(1, width)))
    return Ust.snap(knob, knob.min + f * (knob.max - knob.min))
  }

  Rectangle {
    id: track
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    height: 4
    radius: 2
    color: Theme.line2

    Rectangle {
      width: parent.width * sl.frac
      height: parent.height
      radius: 2
      color: Theme.blue
    }
  }
  Rectangle {
    width: 14
    height: 14
    radius: 7
    anchors.verticalCenter: parent.verticalCenter
    x: (sl.width - width) * sl.frac
    color: sl.dragging ? Theme.fg : Theme.fg2
    border.width: 2
    border.color: Theme.blue
  }

  MouseArea {
    anchors.fill: parent
    enabled: sl.active
    cursorShape: Qt.PointingHandCursor
    onPressed: function(mouse) { sl.dragging = true; sl.dragValue = sl.valueAt(mouse.x) }
    onPositionChanged: function(mouse) { if (pressed) sl.dragValue = sl.valueAt(mouse.x) }
    onReleased: {
      sl.dragging = false
      if (Math.abs(sl.dragValue - sl.value) > 1e-9) sl.committed(sl.dragValue)
    }
    onCanceled: sl.dragging = false
  }
}
