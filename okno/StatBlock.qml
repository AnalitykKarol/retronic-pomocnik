import QtQuick

// Licznik (makieta: .stat): etykieta wersalikami i wartość 15 px; `suffix` to przyciemniony dopisek ("/ limit 20").
Column {
  id: stat

  property string label: ""
  property string value: ""
  property string suffix: ""
  property color valueColor: Theme.fg

  spacing: 3

  Text {
    text: stat.label.toUpperCase()
    color: Theme.dim
    font.family: Theme.font
    font.pixelSize: Theme.tiny
    font.letterSpacing: 1
  }
  Item {
    width: valueText.implicitWidth + (stat.suffix !== "" ? suffixText.implicitWidth + 6 : 0)
    height: valueText.implicitHeight
    Text {
      id: valueText
      text: stat.value
      color: stat.valueColor
      font.family: Theme.font
      font.pixelSize: 15
      font.bold: true
    }
    Text {
      id: suffixText
      visible: stat.suffix !== ""
      anchors.left: valueText.right
      anchors.leftMargin: 6
      anchors.baseline: valueText.baseline
      text: stat.suffix
      color: Theme.dim
      font.family: Theme.font
      font.pixelSize: Theme.small
    }
  }
}
