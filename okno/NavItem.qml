import QtQuick

// Pozycja menu sekcji (pasek boczny). `soon` = sekcja z późniejszej fazy: widoczna, wyszarzona, z etykietą fazy, bez kliknięcia.
Rectangle {
  id: item

  property string icon: ""
  property string label: ""
  property bool current: false
  property string soon: ""            // "F3" / "F4" => wyszarzona
  property int count: 0               // licznik (np. dzisiejsze sygnały ratunku), 0 = brak plakietki

  signal chosen()

  implicitHeight: 34
  radius: 6
  color: current ? Theme.sur2 : (mouse.containsMouse && soon === "" ? Theme.alpha(Theme.sur2, 0.5) : "transparent")
  opacity: soon !== "" ? 0.5 : 1

  Text {
    id: ic
    anchors.left: parent.left
    anchors.leftMargin: 10
    anchors.verticalCenter: parent.verticalCenter
    width: 16
    horizontalAlignment: Text.AlignHCenter
    text: item.icon
    color: item.current ? Theme.blue : Theme.dim
    font.family: Theme.font
    font.pixelSize: Theme.body
  }
  Text {
    anchors.left: ic.right
    anchors.leftMargin: 10
    anchors.verticalCenter: parent.verticalCenter
    text: item.label
    color: item.current ? Theme.fg : Theme.fg2
    font.family: Theme.font
    font.pixelSize: Theme.body
  }
  Rectangle {
    visible: item.count > 0 || item.soon !== ""
    anchors.right: parent.right
    anchors.rightMargin: 10
    anchors.verticalCenter: parent.verticalCenter
    width: badge.implicitWidth + 12
    height: 16
    radius: 8
    color: item.soon !== "" ? Theme.line : Theme.alpha(Theme.warn, 0.2)
    Text {
      id: badge
      anchors.centerIn: parent
      text: item.soon !== "" ? item.soon : String(item.count)
      color: item.soon !== "" ? Theme.dim : Theme.warn
      font.family: Theme.font
      font.pixelSize: Theme.tiny
    }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    enabled: item.soon === ""
    cursorShape: Qt.PointingHandCursor
    onClicked: item.chosen()
  }
}
