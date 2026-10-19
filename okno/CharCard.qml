import QtQuick
import "OknoModel.js" as Model

// Karta postaci w pasku bocznym (makieta wariant B): kropka stanu, nick, instancja, mapa · tryb, mini HP/MP. Klik = wybór postaci.
Rectangle {
  id: card

  property var inst: ({})
  property string klasa: "brak"
  property bool selected: false

  signal chosen()

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
      Text {
        id: nick
        anchors.left: dot.right
        anchors.leftMargin: 8
        anchors.right: tag.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        text: Model.nickOf(card.inst)
        color: Theme.fg
        font.family: Theme.font
        font.pixelSize: Theme.body
        font.bold: true
        elide: Text.ElideRight
      }
      Chip {
        id: tag
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        small: true
        label: Model.instanceLabel(card.inst)
      }
    }

    Text {
      width: parent.width
      topPadding: 4
      bottomPadding: 8
      text: Model.cardSubtitle(card.inst)
      color: Theme.dim
      font.family: Theme.font
      font.pixelSize: Theme.tiny
      elide: Text.ElideRight
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
