pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "PrzegladModel.js" as Prz

// Przegląd (spec wtyczka-paska/specs/2026-10-22-retronic-przeglad.md, F2; makieta wariant A „tabela”): co na czym stoi, wszystkie postacie naraz.
// Liczniki u góry, filtry (wszystkie / w grze / z alarmem), tabela w grupach „W GRZE” (dane na żywo) i „OFFLINE” (ostatnio znane, wyszarzone).
// Okno niczego tu nie liczy poza prezentacją: stany, nadzór, zab/h i exp/h przychodzą z `okno_api stan` (przeglad, ostatnie), logika w PrzegladModel.js.
// Instancje test:true są w tabeli, ale poza sumami. Klik w wiersz = Sesja gry tej postaci. Dane odświeża Backend (co 5 s, wybrana co 2 s).
// Tabela ma szerokość z makiety (14 kolumn); w wąskim oknie przewija się poziomo.
Item {
  id: view

  required property var ctl

  property string filter: "wszystkie"

  readonly property var now: ctl.refreshedAt || new Date()
  readonly property var rows: Prz.rowsOf(ctl.instances, now)
  readonly property var counts: Prz.countersOf(ctl.instances)
  readonly property var filterCounts: Prz.filterCounts(rows)
  readonly property var groups: Prz.groupsOf(rows, filter)

  // kolumny jak w makiecie: POSTAĆ · STAN · SPOT·PIĘTRO · TRYB · LEVEL · ML · HP · MANA · EXP/H · NA SPOCIE/OSTATNI · ZAB/H · ALARM (elastyczna) · NADZÓR
  // (GDZIE, czyli współrzędne, zniknęło z tabeli 23.10: jest w widoku postaci i w podpowiedzi po najechaniu na wiersz; EXP/H stoi tam, gdzie było GDZIE,
  // żeby było widać przy każdej szerokości okna)
  readonly property var fixedW: [220, 190, 190, 130, 80, 76, 140, 130, 76, 190, 56]
  readonly property int lastW: 190
  readonly property int gap: 14
  readonly property int pad: 22
  readonly property int fixedSum: 220 + 190 + 190 + 130 + 80 + 76 + 140 + 130 + 76 + 190 + 56
  readonly property int alarmW: Math.max(220, flick.width - (fixedSum + lastW + 12 * gap + 2 * pad))
  readonly property int tableW: fixedSum + alarmW + lastW + 12 * gap + 2 * pad
  readonly property var colW: fixedW.concat([alarmW, lastW])
  readonly property var heads: ["postać", "stan", "spot · piętro", "tryb", "level", "ML", "HP", "mana", "exp/h", "na spocie / ostatni", "zab/h", "ostatni alarm", "nadzór"]

  function textColor(tone) { return Theme.tone(tone) }

  ColumnLayout {
    anchors.fill: parent
    spacing: 0

    SectionHeader {
      Layout.fillWidth: true
      title: "Przegląd · " + Prz.postaciLabel(view.rows.length)
      subtitle: "co na czym stoi: w grze u góry, offline z ostatnimi znanymi danymi · klik w wiersz otwiera postać"

      Chip {
        objectName: "filtr-wszystkie"
        clickable: true
        on: view.filter === "wszystkie"
        label: "wszystkie " + view.filterCounts["wszystkie"]
        textColor: view.filter === "wszystkie" ? Theme.fg : Theme.fg2
        onActivated: view.filter = "wszystkie"
      }
      Chip {
        objectName: "filtr-w-grze"
        clickable: true
        on: view.filter === "w grze"
        label: "w grze " + view.filterCounts["w grze"]
        textColor: view.filter === "w grze" ? Theme.fg : Theme.fg2
        onActivated: view.filter = "w grze"
      }
      Chip {
        objectName: "filtr-z-alarmem"
        clickable: true
        on: view.filter === "z alarmem"
        label: "z alarmem " + view.filterCounts["z alarmem"]
        textColor: view.filter === "z alarmem" ? Theme.fg : Theme.fg2
        onActivated: view.filter = "z alarmem"
      }
    }

    // ---------- liczniki (bez instancji testowych)
    Rectangle {
      Layout.fillWidth: true
      Layout.preferredHeight: statsRow.implicitHeight + 28
      color: "transparent"
      Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }

      Flow {
        id: statsRow
        objectName: "przeglad-liczniki"
        anchors.left: parent.left
        anchors.leftMargin: 22
        anchors.right: parent.right
        anchors.rightMargin: 22
        anchors.verticalCenter: parent.verticalCenter
        spacing: 34

        StatBlock { label: "W grze"; value: String(view.counts.inGame); suffix: "/ " + view.counts.total; objectName: "licznik-w-grze" }
        StatBlock { label: "Bot działa"; value: String(view.counts.bot); valueColor: Theme.ok; objectName: "licznik-bot" }
        StatBlock { label: "Karol gra"; value: String(view.counts.karol); valueColor: Theme.cyan; objectName: "licznik-karol" }
        StatBlock { label: "Zatrzymane"; value: String(view.counts.stopped); valueColor: Theme.warn; objectName: "licznik-zatrzymane" }
        StatBlock { label: "Offline"; value: String(view.counts.offline); suffix: Prz.suspendedNote(view.counts); valueColor: Theme.fg2; objectName: "licznik-offline" }
        StatBlock {
          label: "Exp/h razem"
          value: view.counts.expBots > 0 ? Prz.groupDigits(view.counts.expH) : "—"
          suffix: view.counts.expBots > 0 ? Prz.expBotsNote(view.counts) : ""
          valueColor: view.counts.expBots > 0 ? Theme.fg : Theme.dim2
          objectName: "licznik-exp"
        }
        StatBlock { label: "Ratunek dziś"; value: String(view.counts.rescue); valueColor: view.counts.rescue > 0 ? Theme.warn : Theme.dim2; objectName: "licznik-ratunek" }
      }
    }

    // ---------- tabela (poziome i pionowe przewijanie; nagłówek kolumn przewija się z treścią)
    Flickable {
      id: flick
      objectName: "przeglad-tabela"
      Layout.fillWidth: true
      Layout.fillHeight: true
      contentWidth: view.tableW
      contentHeight: table.implicitHeight + 24
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      flickableDirection: Flickable.AutoFlickDirection
      ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
      ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }

      Column {
        id: table
        width: view.tableW

        // nagłówek kolumn
        Rectangle {
          width: parent.width
          height: 31
          color: Theme.bg
          Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
          Row {
            x: view.pad
            height: parent.height
            spacing: view.gap
            Repeater {
              model: view.heads
              delegate: Item {
                id: headCell
                required property int index
                required property string modelData
                width: view.colW[index]
                height: 31
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.right: (index === 4 || index === 8 || index === 10) ? parent.right : undefined
                  text: headCell.modelData.toUpperCase()
                  color: Theme.dim2
                  font.family: Theme.font
                  font.pixelSize: Theme.tiny
                  font.letterSpacing: 1
                }
              }
            }
          }
        }

        Repeater {
          model: view.groups
          delegate: Column {
            id: grp
            required property var modelData
            width: table.width

            Rectangle {
              objectName: "grupa-" + grp.modelData.key
              width: parent.width
              height: 30
              color: Theme.bg2
              Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
              Row {
                x: view.pad
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                Text { text: grp.modelData.title; color: Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.tiny; font.letterSpacing: 1; font.bold: true }
                Text { text: "· " + grp.modelData.count; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.tiny }
                Text { text: "— " + grp.modelData.note; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.tiny }
              }
            }

            Repeater {
              model: grp.modelData.rows
              delegate: TableRow {
                required property var modelData
                row: modelData
                width: grp.width
              }
            }
          }
        }

        Text {
          visible: view.groups.length === 0
          x: view.pad
          topPadding: 14
          text: view.rows.length === 0 ? "brak postaci" : "brak postaci dla tego filtra"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.body
        }

        Text {
          x: view.pad
          topPadding: 10
          width: Math.min(parent.width, flick.width) - 2 * view.pad
          wrapMode: Text.Wrap
          text: "ML „?”: bot dziś nie odczytuje magic levelu (odczyt czeka na osobną fazę). Zab/h i exp/h liczone z bieżącej sesji bota; offline pokazuje „—”, "
                + "tempo ostatniej sesji jest w szczegółach postaci. „~” przy max HP/MP = wartość przybliżona z telemetrii."
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.small
        }
      }
    }
  }

  // ---------------------------------------------------------------- wiersz tabeli
  component TableRow: Rectangle {
    id: tr

    required property var row
    readonly property bool off: !row.inGame

    objectName: "wiersz-" + row.id
    height: 40
    color: mouse.containsMouse ? Theme.alpha(Theme.blue, 0.07) : (off ? Theme.alpha(Theme.bg2, 0.35) : "transparent")

    function tryClick() { view.ctl.openChar(row.id) }

    Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
    Rectangle { visible: mouse.containsMouse; anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; width: 3; color: Theme.blue }

    MouseArea {
      id: mouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: tr.tryClick()
      // współrzędne (dawna kolumna GDZIE) w podpowiedzi; offline: ostatnia znana pozycja z `ostatnie`, brak = bez podpowiedzi
      ToolTip.visible: containsMouse && tr.row.where !== "—"
      ToolTip.delay: 600
      ToolTip.text: (tr.off ? "Ostatnio znane miejsce: " : "Gdzie: ") + tr.row.where
    }

    Row {
      x: view.pad
      height: parent.height
      spacing: view.gap

      // 0 POSTAĆ
      Cell {
        w: view.colW[0]
        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: 8
          Rectangle { width: 9; height: 9; radius: 4.5; anchors.verticalCenter: parent.verticalCenter; color: Theme.tone(tr.row.dot) }
          Text { text: tr.row.nick; color: tr.off ? Theme.fg2 : Theme.fg; font.family: Theme.font; font.pixelSize: Theme.body; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
          Text { text: tr.row.idLabel; color: Theme.dim2; font.family: Theme.font; font.pixelSize: Theme.small; anchors.verticalCenter: parent.verticalCenter }
          Rectangle {
            visible: tr.row.test
            height: 16; width: testText.implicitWidth + 10; radius: 8; anchors.verticalCenter: parent.verticalCenter
            color: Theme.line
            Text { id: testText; anchors.centerIn: parent; text: "test"; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.tiny }
          }
        }
      }
      // 1 STAN
      Cell {
        w: view.colW[1]
        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: 8
          Rectangle {
            objectName: "pill-" + tr.row.id
            height: 20; width: pillText.implicitWidth + 16; radius: 10; anchors.verticalCenter: parent.verticalCenter
            color: tr.row.pill.tone === "dim" ? Theme.sur2 : Theme.alpha(Theme.tone(tr.row.pill.tone), 0.14)
            Text { id: pillText; anchors.centerIn: parent; text: tr.row.pill.label; color: Theme.tone(tr.row.pill.tone); font.family: Theme.font; font.pixelSize: Theme.small; font.bold: true }
          }
          Text { text: tr.row.since; visible: text !== ""; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small; anchors.verticalCenter: parent.verticalCenter }
        }
      }
      // 2 SPOT · PIĘTRO
      Cell {
        w: view.colW[2]
        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: 6
          Text { text: tr.row.spot !== "" ? tr.row.spot : "—"; color: tr.off ? Theme.dim : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body }
          Text { visible: tr.row.floor !== ""; text: "· " + tr.row.floor; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.body }
        }
      }
      // 3 TRYB
      Cell {
        w: view.colW[3]
        Text { anchors.verticalCenter: parent.verticalCenter; text: tr.row.mode !== "" ? tr.row.mode : "—"; color: tr.off ? Theme.dim : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body }
      }
      // 4 LEVEL (po prawej)
      Cell {
        w: view.colW[4]
        Row {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          spacing: 6
          Text { text: tr.row.level === null ? "—" : String(tr.row.level); color: tr.row.level === null ? Theme.dim2 : (tr.off ? Theme.fg2 : Theme.fg); font.family: Theme.font; font.pixelSize: Theme.body; font.bold: true }
          Text { visible: tr.row.levelPct !== null; text: tr.row.levelPct + "%"; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small; anchors.verticalCenter: parent.verticalCenter }
        }
      }
      // 5 ML
      Cell {
        w: view.colW[5]
        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: 6
          Text { text: tr.row.ml; color: tr.row.ml === "?" ? Theme.dim2 : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body }
          Text { visible: tr.row.mlPct !== null; text: tr.row.mlPct + "%"; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small; anchors.verticalCenter: parent.verticalCenter }
        }
      }
      // 6 HP, 7 MANA
      Cell { w: view.colW[6]; Resource { res: tr.row.hp; barColor: Theme.bad } }
      Cell { w: view.colW[7]; Resource { res: tr.row.mana; barColor: Theme.blue } }
      // 8 EXP/H (po prawej; to samo pole co dawniej kolumna z prawej, groupDigits jak kafelek „Exp/h razem”, brak/offline/zawieszona = „—”)
      Cell {
        w: view.colW[8]
        Text {
          objectName: "exp-h-" + tr.row.id
          anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
          text: tr.row.expH === null ? "—" : Prz.groupDigits(tr.row.expH)
          color: tr.row.expH === null ? Theme.dim2 : Theme.fg; font.family: Theme.font; font.pixelSize: Theme.body; font.bold: tr.row.expH !== null
        }
      }
      // 9 NA SPOCIE / OSTATNI
      Cell {
        w: view.colW[9]
        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: 6
          Text { visible: tr.row.spotTime.pre !== ""; text: tr.row.spotTime.pre; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.body }
          Text { visible: tr.row.spotTime.main !== ""; text: tr.row.spotTime.main; color: tr.row.spotTime.dim ? Theme.dim2 : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body }
          Text { visible: tr.row.spotTime.post !== ""; text: tr.row.spotTime.post; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.body }
        }
      }
      // 10 ZAB/H (po prawej)
      Cell {
        w: view.colW[10]
        Text {
          anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
          text: tr.row.zabH === null ? "—" : String(Math.round(tr.row.zabH))
          color: tr.row.zabH === null ? Theme.dim2 : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body
        }
      }
      // 11 OSTATNI ALARM
      Cell {
        w: view.colW[11]
        Text { visible: tr.row.alarm === null; anchors.verticalCenter: parent.verticalCenter; text: "—"; color: Theme.dim2; font.family: Theme.font; font.pixelSize: Theme.body }
        Text {
          id: alarmTime
          visible: tr.row.alarm !== null
          anchors.verticalCenter: parent.verticalCenter
          text: tr.row.alarm ? tr.row.alarm.time : ""
          color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.body
        }
        Text {
          visible: tr.row.alarm !== null
          anchors.left: alarmTime.right
          anchors.leftMargin: 8
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          text: tr.row.alarm ? tr.row.alarm.text : ""
          color: tr.row.alarm ? Theme.tone(tr.row.alarm.tone) : Theme.dim
          font.family: Theme.font; font.pixelSize: Theme.body
          elide: Text.ElideRight
        }
      }
      // 12 NADZÓR
      Cell {
        w: view.colW[12]
        Text { anchors.verticalCenter: parent.verticalCenter; text: tr.row.supervision.text; color: Theme.tone(tr.row.supervision.tone); font.family: Theme.font; font.pixelSize: Theme.body }
      }
    }
  }

  component Cell: Item {
    property int w: 100
    width: w
    height: 40
    clip: true
  }

  // pasek zasobu (HP/MANA): na żywo 64 px + „cur/max”, offline „max N” bez paska
  component Resource: Item {
    id: resItem
    property var res: ({ live: false, text: "—" })
    property color barColor: Theme.blue
    anchors.verticalCenter: parent ? parent.verticalCenter : undefined
    height: 20
    width: parent ? parent.width : 0

    Row {
      visible: resItem.res.live
      anchors.verticalCenter: parent.verticalCenter
      spacing: 8
      Rectangle {
        width: 64; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter
        color: Theme.line
        clip: true
        Rectangle { width: parent.width * resItem.res.frac; height: parent.height; radius: 3; color: resItem.barColor }
      }
      Text {
        textFormat: Text.StyledText
        text: resItem.res.live ? resItem.res.cur + "<font color=\"" + Theme.dim + "\">/" + resItem.res.max + "</font>" : ""
        color: Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body
      }
    }
    Text {
      visible: !resItem.res.live
      anchors.verticalCenter: parent.verticalCenter
      textFormat: Text.StyledText
      text: resItem.res.text.indexOf("max ") === 0 ? "max <font color=\"" + Theme.fg2 + "\">" + resItem.res.text.substring(4) + "</font>" : resItem.res.text
      color: resItem.res.text === "—" ? Theme.dim2 : Theme.dim
      font.family: Theme.font; font.pixelSize: Theme.body
    }
  }
}
