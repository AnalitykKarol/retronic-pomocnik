pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "PrzegladModel.js" as Prz
import "SpotkaniaModel.js" as Spo

// Przegląd (spec wtyczka-paska/specs/2026-10-22-retronic-przeglad.md, F2; makieta wariant A „tabela”): co na czym stoi, wszystkie postacie naraz.
// Liczniki u góry, filtry (wszystkie / w grze / z alarmem / stracone), wybór sortowania (domyślnie poziom ↓, 25.10), tabela w grupach „W GRZE” (dane na żywo) i „OFFLINE” (ostatnio znane, wyszarzone).
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
  readonly property var groups: Prz.groupsOf(rows, filter, ctl.sortKey)       // sortowanie (25.10): jedno ustawienie Backend.sortKey, wspólne z listą w pasku bocznym

  // kolumny jak w makiecie: POSTAĆ · STAN · SPOT·PIĘTRO · TRYB · LEVEL · ML · HP · MANA · EXP/H · NA SPOCIE/OSTATNI · ZAB/H · ALARM (elastyczna) · NADZÓR
  // (GDZIE, czyli współrzędne, zniknęło z tabeli 23.10: jest w widoku postaci i w podpowiedzi po najechaniu na wiersz; EXP/H stoi tam, gdzie było GDZIE,
  // żeby było widać przy każdej szerokości okna)
  // 26.10 (Karol): dołożony blok SPOTKANIA (dwie linie, po prawej stronie obu linii wiersza); żeby tabela nadal mieściła się bez poziomego przewijania w oknie ok. 1660 px
  // (obszar treści ok. 1400 px), zwężone: postać, stan, blanki · runy, level, ML, exp/h, zab/h oraz druga linia (spot, tryb, na spocie, nadzór). HP i mana bez zmian.
  readonly property var colW: [180, 200, 170, 76, 68, 120, 120, 72, 52]
  readonly property int gap: 10
  readonly property int pad: 22
  readonly property int spoW: 190                                  // blok SPOTKANIA: x = tableW - pad - spoW
  readonly property int tableW: Math.max(flick.width, 2 * pad + 1050 + 9 * gap + spoW + 10)     // 1050 = suma colW; 1392 px minimum
  // druga linia wiersza: spot, tryb, na spocie, alarm (elastyczna), nadzór; zaczyna się pod kolumną „stan”, kończy przed blokiem SPOTKANIA
  readonly property int alarmW: Math.max(200, tableW - 2 * pad - (colW[0] + gap) - (170 + 150 + 170 + 130) - 4 * gap - (spoW + gap))
  readonly property var colWB: [170, 150, 170, alarmW, 130]
  readonly property var instById: {
    var m = {}
    var l = ctl.instances || []
    for (var i = 0; i < l.length; i++) m[l[i].id] = l[i]
    return m
  }
  readonly property var heads: ["postać", "stan", "blanki · runy", "level", "ML", "HP", "mana", "exp/h", "zab/h"]
  readonly property var headsB: ["spot · piętro", "tryb", "na spocie / ostatni", "ostatni alarm", "nadzór"]
  readonly property var headsSpo: ["spotkań · widziani", "próg bota · bywalec"]

  function textColor(tone) { return Theme.tone(tone) }

  ColumnLayout {
    anchors.fill: parent
    spacing: 0

    SectionHeader {
      Layout.fillWidth: true
      title: "Przegląd · " + Prz.postaciLabel(view.filterCounts["wszystkie"])       // stracone ukryte (25.10): liczymy tylko widoczne, stracone mają własny chip
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
      Chip {
        objectName: "filtr-stracone"
        clickable: true
        on: view.filter === "stracone"
        label: "stracone " + view.filterCounts["stracone"]
        textColor: view.filter === "stracone" ? Theme.fg : Theme.fg2
        onActivated: view.filter = "stracone"
      }
    }

    // ---------- sortowanie (25.10): chipy pod nagłówkiem; to samo ustawienie porządkuje listę postaci w pasku bocznym i przeżywa restart okna
    Rectangle {
      Layout.fillWidth: true
      Layout.preferredHeight: 34
      color: "transparent"
      Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }

      Row {
        objectName: "przeglad-sortowanie"
        x: 22
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8

        Text {
          anchors.verticalCenter: parent.verticalCenter
          text: "SORTUJ"
          color: Theme.dim
          font.family: Theme.font
          font.pixelSize: Theme.tiny
          font.letterSpacing: 1
          rightPadding: 4
        }
        Repeater {
          model: Prz.SORTS
          delegate: Chip {
            required property var modelData
            objectName: "sort-" + modelData.key
            small: true
            clickable: true
            on: view.ctl.sortKey === modelData.key
            label: modelData.label
            textColor: on ? Theme.fg : Theme.fg2
            onActivated: view.ctl.setSort(modelData.key)
          }
        }
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

        // nagłówek kolumn (dwie linie, jak wiersze)
        Rectangle {
          width: parent.width
          height: 46
          color: Theme.bg
          Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Theme.line }
          Column {
            x: parent.width - view.pad - view.spoW
            width: view.spoW
            Repeater {
              model: view.headsSpo
              delegate: Item {
                id: headSpo
                required property string modelData
                width: view.spoW
                height: 23
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: headSpo.modelData.toUpperCase()
                  color: Theme.dim2
                  font.family: Theme.font
                  font.pixelSize: Theme.tiny
                  font.letterSpacing: 1
                }
              }
            }
          }
          Row {
            x: view.pad
            y: 0
            height: 23
            spacing: view.gap
            Repeater {
              model: view.heads
              delegate: Item {
                id: headCell
                required property int index
                required property string modelData
                width: view.colW[index]
                height: 23
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.right: (index === 3 || index === 7 || index === 8) ? parent.right : undefined
                  text: headCell.modelData.toUpperCase()
                  color: Theme.dim2
                  font.family: Theme.font
                  font.pixelSize: Theme.tiny
                  font.letterSpacing: 1
                }
              }
            }
          }
          Row {
            x: view.pad + view.colW[0] + view.gap
            y: 23
            height: 23
            spacing: view.gap
            Repeater {
              model: view.headsB
              delegate: Item {
                id: headCellB
                required property int index
                required property string modelData
                width: view.colWB[index]
                height: 23
                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: headCellB.modelData.toUpperCase()
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
    height: 74
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
      ToolTip.visible: containsMouse && tr.row.where !== "—" && !spoBlock.over
      ToolTip.delay: 600
      ToolTip.text: (tr.off ? "Ostatnio znane miejsce: " : "Gdzie: ") + tr.row.where
    }

    Row {
      x: view.pad
      y: 2
      height: 36
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
          // „Zaloguj postać” (24.10): tylko dla postaci niezalogowanej (offline albo ekran logowania), nie straconej i nie głównej; szary z powodem, gdy trwa inne logowanie
          // albo inna akcja tej postaci. Loguje do gry BEZ bota (Backend.runLogin -> zaloguj_postac.sh). Klik nie otwiera wiersza (własny MouseArea Btn).
          Btn {
            id: loginBtn
            readonly property var spec: view.ctl.loginState(tr.row.id)
            objectName: "zaloguj-" + tr.row.id
            visible: (spec.reason === "" || spec.reason === "other" || spec.reason === "busy" || spec.reason === "login")
            compact: true
            tone: "neutral"
            label: spec.label
            active: spec.enabled
            busy: spec.busy
            anchors.verticalCenter: parent.verticalCenter
            ToolTip.visible: hovered
            ToolTip.delay: 400
            ToolTip.text: spec.hint
            onActivated: view.ctl.runLogin(tr.row.id)
          }
        }
      }
      // 11 BLANKI · RUNY (25.10: ile blanków i gotowych run ma postać, odczyt pamięci; mało blanków = żółty)
      Cell {
        w: view.colW[2]
        Text {
          objectName: "runy-" + tr.row.id
          anchors.verticalCenter: parent.verticalCenter
          text: tr.row.runy !== "" ? tr.row.runy : "—"
          color: tr.row.runy === "" ? Theme.dim2 : (tr.row.runyLow ? Theme.warn : Theme.fg2)
          font.family: Theme.font; font.pixelSize: Theme.body
        }
      }
      // 4 LEVEL (po prawej)
      Cell {
        w: view.colW[3]
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
        w: view.colW[4]
        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: 6
          Text { text: tr.row.ml; color: tr.row.ml === "?" ? Theme.dim2 : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body }
          Text { visible: tr.row.mlPct !== null; text: tr.row.mlPct + "%"; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.small; anchors.verticalCenter: parent.verticalCenter }
        }
      }
      // 6 HP, 7 MANA
      Cell { w: view.colW[5]; Resource { res: tr.row.hp; barColor: Theme.bad } }
      Cell { w: view.colW[6]; Resource { res: tr.row.mana; barColor: Theme.blue } }
      // 8 EXP/H (po prawej; to samo pole co dawniej kolumna z prawej, groupDigits jak kafelek „Exp/h razem”, brak/offline/zawieszona = „—”)
      Cell {
        w: view.colW[7]
        Text {
          objectName: "exp-h-" + tr.row.id
          anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
          text: tr.row.expH === null ? "—" : Prz.groupDigits(tr.row.expH)
          color: tr.row.expH === null ? Theme.dim2 : Theme.fg; font.family: Theme.font; font.pixelSize: Theme.body; font.bold: tr.row.expH !== null
        }
      }
      // 10 ZAB/H (po prawej)
      Cell {
        w: view.colW[8]
        Text {
          anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
          text: tr.row.zabH === null ? "—" : String(Math.round(tr.row.zabH))
          color: tr.row.zabH === null ? Theme.dim2 : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body
        }
      }
    }

    // SPOTKANIA (26.10): dwie linie po prawej stronie wiersza, te same dane i podpowiedź co na karcie postaci (SpotkaniaModel.przegladCell);
    // poza grą / Karol gra / brak sekcji: „—” z podpowiedzią (powód braku danych), bez zgadywania liczb
    Item {
      id: spoBlock
      readonly property var cell: Spo.przegladCell(view.instById[tr.row.id], tr.row.inGame)
      objectName: "przeglad-spotkania-" + tr.row.id
      readonly property string line1Text: cell.line1
      readonly property string line2Text: cell.line2
      readonly property string tipText: cell.tip
      readonly property bool hot: cell.hot
      readonly property bool over: spoHover.hovered
      x: tr.width - view.pad - view.spoW
      y: 0
      width: view.spoW
      height: tr.height
      clip: true
      Text {
        x: 0; y: 11; width: parent.width; height: 20
        verticalAlignment: Text.AlignVCenter
        text: spoBlock.cell.line1
        color: spoBlock.cell.ok ? Theme.fg2 : Theme.dim2
        font.family: Theme.font; font.pixelSize: Theme.small
        elide: Text.ElideRight
      }
      Text {
        visible: spoBlock.cell.line2 !== ""
        x: 0; y: 44; width: parent.width; height: 20
        verticalAlignment: Text.AlignVCenter
        text: spoBlock.cell.line2
        color: spoBlock.cell.hot ? Theme.warn : Theme.dim
        font.bold: spoBlock.cell.hot
        font.family: Theme.font; font.pixelSize: Theme.small
        elide: Text.ElideRight
      }
      HoverHandler { id: spoHover }                         // pasywny: nie zabiera kliknięcia wierszowi
      ToolTip.visible: spoHover.hovered && spoBlock.cell.tip !== ""
      ToolTip.delay: 500
      ToolTip.text: spoBlock.cell.tip
    }

    // druga linia: spot, tryb, czas na spocie, alarm, nadzór (pod kolumnami „stan” i dalej)
    Row {
      x: view.pad + view.colW[0] + view.gap
      y: 38
      height: 34
      spacing: view.gap

      // 2 SPOT · PIĘTRO
      Cell {
        w: view.colWB[0]
        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: 6
          Text { text: tr.row.spot !== "" ? tr.row.spot : "—"; color: tr.off ? Theme.dim : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body }
          Text { visible: tr.row.floor !== ""; text: "· " + tr.row.floor; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.body }
        }
      }
      // 3 TRYB
      Cell {
        w: view.colWB[1]
        Text { anchors.verticalCenter: parent.verticalCenter; text: tr.row.mode !== "" ? tr.row.mode : "—"; color: tr.off ? Theme.dim : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body }
      }
      // 9 NA SPOCIE / OSTATNI
      Cell {
        w: view.colWB[2]
        Row {
          anchors.verticalCenter: parent.verticalCenter
          spacing: 6
          Text { visible: tr.row.spotTime.pre !== ""; text: tr.row.spotTime.pre; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.body }
          Text { visible: tr.row.spotTime.main !== ""; text: tr.row.spotTime.main; color: tr.row.spotTime.dim ? Theme.dim2 : Theme.fg2; font.family: Theme.font; font.pixelSize: Theme.body }
          Text { visible: tr.row.spotTime.post !== ""; text: tr.row.spotTime.post; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.body }
        }
      }
      // 12 OSTATNI ALARM
      Cell {
        w: view.colWB[3]
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
      // 13 NADZÓR
      Cell {
        w: view.colWB[4]
        Text { anchors.verticalCenter: parent.verticalCenter; text: tr.row.supervision.text; color: Theme.tone(tr.row.supervision.tone); font.family: Theme.font; font.pixelSize: Theme.body }
      }
    }
  }

  component Cell: Item {
    property int w: 100
    width: w
    height: parent ? parent.height : 36
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
