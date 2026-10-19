import QtQuick

// Pigułka (.chip w makiecie): etykieta, opcjonalnie klikalna (filtry listy).
Rectangle {
  id: chip

  property string label: ""
  property bool clickable: false
  property bool small: false
  property color textColor: Theme.fg2

  signal activated()

  implicitWidth: text.implicitWidth + (small ? 14 : 18)
  implicitHeight: small ? 18 : 22
  radius: height / 2
  color: Theme.sur2
  border.width: 1
  border.color: clickable && mouse.containsMouse ? Theme.dim : Theme.line

  Text {
    id: text
    anchors.centerIn: parent
    text: chip.label
    color: chip.textColor
    font.family: Theme.font
    font.pixelSize: chip.small ? Theme.tiny : Theme.small
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    enabled: chip.clickable
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: chip.activated()
  }
}
