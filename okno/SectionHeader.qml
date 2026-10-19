import QtQuick

// Nagłówek sekcji (makieta: .mh): tytuł 16 px, opis pod spodem, po prawej dowolna treść (chipy).
Rectangle {
  id: head

  property string title: ""
  property string subtitle: ""
  default property alias rightContent: right.data

  implicitHeight: 69
  color: "transparent"

  Rectangle {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    height: 1
    color: Theme.line
  }

  Column {
    anchors.left: parent.left
    anchors.leftMargin: 22
    anchors.right: right.left
    anchors.rightMargin: 16
    anchors.verticalCenter: parent.verticalCenter
    spacing: 3

    Text {
      width: parent.width
      text: head.title
      color: Theme.fg
      font.family: Theme.font
      font.pixelSize: Theme.title
      font.bold: true
      elide: Text.ElideRight
    }
    Text {
      width: parent.width
      text: head.subtitle
      color: Theme.dim
      font.family: Theme.font
      font.pixelSize: Theme.small + 1
      elide: Text.ElideRight
    }
  }

  Row {
    id: right
    anchors.right: parent.right
    anchors.rightMargin: 22
    anchors.verticalCenter: parent.verticalCenter
    spacing: 10
  }
}
