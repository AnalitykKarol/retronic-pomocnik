import QtQuick
import "OknoModel.js" as Model

// Karta postaci w pasku bocznym (makieta wariant B): kropka stanu, nick, instancja, mapa · tryb, lvl, mini HP/MP. Klik = wybór postaci.
// Klik w nick = podgląd tej instancji (`previewRequested`, spec 2026-10-20-retronic-lvl-i-podglad.md Q1); znacznik przy nicku jak na pasku:
// podgląd otwarty = akcent, zamknięty = przygaszony, brak sesji (albo główna) = bez znacznika i nick nieklikalny.
Rectangle {
  id: card

  property var inst: ({})
  property string klasa: "brak"
  property bool selected: false
  property var preview: ({ state: "main", label: "", enabled: false, hint: "" })     // wynik Rules.previewState
  property bool busy: false      // akcja TEJ instancji w toku (ctl.isBusy(id)): nick nie przyjmuje kliknięcia; inne instancje nie wpływają

  readonly property var marker: Model.previewMarker(preview)

  signal chosen()
  signal previewRequested()

  implicitHeight: col.implicitHeight + 22
  radius: 10
  color: Theme.sur
  border.width: 1
  border.color: selected ? Theme.blue : (mouse.containsMouse ? Theme.line2 : Theme.line)

  // delikatna obwódka od środka dla wybranej (box-shadow inset z makiety)
  Rectangle {
    anchors.fill: parent
    anchors.margins: 1
    radius: 9
    color: "transparent"
    border.width: card.selected ? 1 : 0
    border.color: Theme.alpha(Theme.blue, 0.25)
  }

  Column {
    id: col
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.top: parent.top
    anchors.margins: 12
    anchors.topMargin: 11
    spacing: 0

    Item {
      width: parent.width
      height: 20

      Rectangle {
        id: dot
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: 9
        height: 9
        radius: 4.5
        color: Theme.stateColor(card.klasa)
      }
      Item {
        id: nickBox
        anchors.left: dot.right
        anchors.leftMargin: 8
        anchors.right: tag.left
        anchors.rightMargin: 8
        height: parent.height

        Text {
          id: nick
          anchors.verticalCenter: parent.verticalCenter
          width: Math.min(implicitWidth, nickBox.width - (marker.visible ? 16 : 0))
          text: Model.nickOf(card.inst)
          color: Theme.fg
          font.family: Theme.font
          font.pixelSize: Theme.body
          font.bold: true
          font.underline: nickMouse.enabled && nickMouse.containsMouse
          elide: Text.ElideRight
        }
        // znacznik podglądu: wypełnione koło w akcencie = otwarty, pusty pierścień = zamknięty; brak sesji = bez znacznika
        Rectangle {
          id: marker
          objectName: "podglad-znacznik"
          visible: card.marker.visible
          anchors.left: nick.right
          anchors.leftMargin: 7
          anchors.verticalCenter: parent.verticalCenter
          width: 9
          height: 9
          radius: 4.5
          color: card.marker.filled ? Theme.tone(card.marker.tone) : "transparent"
          border.width: 1
          border.color: Theme.tone(card.marker.tone)
        }
        MouseArea {
          id: nickMouse
          objectName: "nick-" + card.inst.id
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          width: marker.visible ? marker.x + marker.width : nick.width
          height: parent.height
          enabled: card.preview.enabled && !card.busy
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          function tryClick() { if (enabled) card.previewRequested() }
          onClicked: tryClick()
        }
      }
      Chip {
        id: tag
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        small: true
        label: Model.instanceLabel(card.inst)
      }
    }

    Item {
      width: parent.width
      height: subtitle.implicitHeight + 12

      Text {
        id: lvl
        objectName: "karta-lvl"
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 4
        text: Model.levelText(card.inst)
        visible: text !== ""
        color: Theme.fg2
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        font.bold: true
      }
      Text {
        id: subtitle
        anchors.left: parent.left
        anchors.right: lvl.visible ? lvl.left : parent.right
        anchors.rightMargin: lvl.visible ? 8 : 0
        anchors.top: parent.top
        anchors.topMargin: 4
        text: Model.cardSubtitle(card.inst)
        color: Theme.dim
        font.family: Theme.font
        font.pixelSize: Theme.tiny
        elide: Text.ElideRight
      }
    }

    Mini { width: parent.width; label: "HP"; fillColor: Theme.bad; value: Model.hpFraction(card.inst) }
    Mini { width: parent.width; label: "MP"; fillColor: Theme.blue; value: Model.mpFraction(card.inst) }
  }

  component Mini: Item {
    id: mini
    property string label: ""
    property color fillColor: Theme.blue
    property real value: 0
    height: 14

    Text {
      id: lbl
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      width: 28
      text: mini.label
      color: Theme.dim
      font.family: Theme.font
      font.pixelSize: Theme.tiny
      font.letterSpacing: 1
    }
    Rectangle {
      anchors.left: lbl.right
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      height: 6
      radius: 3
      color: Theme.line
      clip: true
      Rectangle {
        width: parent.width * mini.value
        height: parent.height
        radius: 3
        color: mini.fillColor
      }
    }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: card.chosen()
  }
}
